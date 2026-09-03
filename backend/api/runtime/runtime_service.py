import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.agent import Agent
from models.attention import AttentionEvent, AttentionType
from models.base import utcnow
from models.session import AgentSession, BoundVia, ExecutionRun, RunStatus
from models.worktree import TaskWorktree

from . import process, worktree
from .mcp_config import McpServerRef, write_mcp_config
from .prompt import build_follow_up_message
from .stream_parser import DomainEvent, parse_stream_line


@dataclass
class RuntimeSettings:
    claude_binary: str = "claude"
    model: str = "claude-sonnet-5"
    permission_mode: str = "acceptEdits"
    runtime_root: Path = field(default_factory=lambda: Path(".agent-office/runtime"))


class RuntimeService:
    """The only service that touches OS processes and long-lived git state."""

    def __init__(self, db: AsyncSession, settings: RuntimeSettings):
        self.db = db
        self.settings = settings
        self._processes: dict[uuid.UUID, process.ManagedProcess] = {}
        self._kill_requested: set[uuid.UUID] = set()
        self._db_lock = asyncio.Lock()

    async def spawn(
        self,
        agent: Agent,
        task_worktree: TaskWorktree,
        allowed_servers: list[McpServerRef],
        initial_message: dict,
        env: dict[str, str] | None = None,
    ) -> ExecutionRun:
        return await self._start_run(agent, task_worktree, allowed_servers, None, initial_message, env)

    async def resume(
        self,
        agent: Agent,
        agent_session: AgentSession,
        task_worktree: TaskWorktree,
        allowed_servers: list[McpServerRef],
        prompt_text: str,
        env: dict[str, str] | None = None,
    ) -> ExecutionRun:
        require_resumable_session(agent, task_worktree, agent_session)
        message = build_follow_up_message(prompt_text)
        return await self._start_run(agent, task_worktree, allowed_servers, agent_session, message, env)

    async def _start_run(self, agent, task_worktree, allowed_servers, resume_session, initial_message, env) -> ExecutionRun:
        mcp_config_path = write_mcp_config(self._agent_runtime_dir(agent), allowed_servers)
        _agent_session, run = await self._open_session_and_run(agent, task_worktree, resume_session)
        await self._launch_process(run, task_worktree, mcp_config_path, resume_session, initial_message, env)
        return run

    async def _open_session_and_run(
        self, agent, task_worktree, resume_session: AgentSession | None
    ) -> tuple[AgentSession, ExecutionRun]:
        before_commit = await worktree.read_head_commit(Path(task_worktree.path))
        agent_session = resume_session or self._open_agent_session(agent, task_worktree)
        bound_via = BoundVia.RESUME if resume_session else BoundVia.SPAWN
        run = self._open_execution_run(agent_session, bound_via, before_commit)
        return agent_session, run

    async def _launch_process(self, run, task_worktree, mcp_config_path, resume_session, initial_message, env) -> None:
        managed = await self._spawn_process(task_worktree, mcp_config_path, resume_session, env)
        run.pid = managed.pid
        await self.commit()
        self._processes[run.id] = managed
        await managed.send_line(initial_message)
        await managed.close_stdin()

    def _agent_runtime_dir(self, agent) -> Path:
        return self.settings.runtime_root / str(agent.id)

    def _open_agent_session(self, agent, task_worktree) -> AgentSession:
        session = AgentSession(
            id=uuid.uuid4(), agent_id=agent.id, task_worktree_id=task_worktree.id, cwd=task_worktree.path
        )
        self.db.add(session)
        return session

    def _open_execution_run(
        self, agent_session: AgentSession, bound_via: BoundVia, before_commit: str
    ) -> ExecutionRun:
        run = ExecutionRun(
            id=uuid.uuid4(),
            agent_session_id=agent_session.id,
            bound_via=bound_via,
            before_head_commit=before_commit,
            started_at=utcnow(),
        )
        self.db.add(run)
        return run

    async def _spawn_process(
        self, task_worktree, mcp_config_path: Path, resume_session: AgentSession | None, env: dict[str, str] | None
    ) -> process.ManagedProcess:
        command = self._build_command(mcp_config_path, resume_session)
        return await process.spawn(command, cwd=Path(task_worktree.path), env=env)

    def _build_command(self, mcp_config_path: Path, resume_session: AgentSession | None) -> list[str]:
        command = self._base_command_args(mcp_config_path)
        if resume_session and resume_session.claude_session_id:
            command += ["--resume", resume_session.claude_session_id]
        return command

    def _base_command_args(self, mcp_config_path: Path) -> list[str]:
        return self._streaming_flags() + self._session_flags(mcp_config_path)

    def _streaming_flags(self) -> list[str]:
        return [
            self.settings.claude_binary,
            "--print",
            "--output-format", "stream-json",
            "--input-format", "stream-json",
            "--include-partial-messages",
            "--verbose",
        ]

    def _session_flags(self, mcp_config_path: Path) -> list[str]:
        return [
            "--model", self.settings.model,
            "--permission-mode", self.settings.permission_mode,
            "--mcp-config", str(mcp_config_path),
            "--strict-mcp-config",
        ]

    async def stream_events(self, run_id: uuid.UUID) -> AsyncIterator[DomainEvent]:
        managed = self._processes[run_id]
        agent_session, run = await self._load_session_and_run(run_id)
        try:
            async for line in managed.iter_stdout_lines():
                event = parse_stream_line(line)
                await self._apply_event(agent_session, event)
                yield event
        finally:
            await self._finalize_run(managed, agent_session, run)

    async def _load_session_and_run(self, run_id: uuid.UUID) -> tuple[AgentSession, ExecutionRun]:
        run = await self.db.get(ExecutionRun, run_id)
        agent_session = await self.db.get(AgentSession, run.agent_session_id)
        return agent_session, run

    async def _apply_event(self, agent_session: AgentSession, event: DomainEvent) -> None:
        if event.kind == "session_started" and event.claude_session_id:
            agent_session.claude_session_id = event.claude_session_id
            await self.commit()

    async def _finalize_run(
        self, managed: process.ManagedProcess, agent_session: AgentSession, run: ExecutionRun
    ) -> None:
        # allow-comment: a caller stopping early (disconnect, cancellation) must still stop the process and record a status, not leak a running Claude session and a stale RUNNING row.
        await managed.terminate()
        exit_code = await managed.wait()
        run.exit_code = exit_code
        run.completed_at = utcnow()
        run.status = self._resolve_final_status(run, exit_code)
        run.after_head_commit = await worktree.read_head_commit(Path(agent_session.cwd))
        self._processes.pop(run.id, None)
        await self.commit()

    def _resolve_final_status(self, run: ExecutionRun, exit_code: int) -> RunStatus:
        # allow-comment: kept off kill_run so only this stream loop's task ever writes to self.db, avoiding a second task racing the same AsyncSession.
        if run.id in self._kill_requested:
            self._kill_requested.discard(run.id)
            return RunStatus.KILLED
        return RunStatus.COMPLETED if exit_code == 0 else RunStatus.FAILED

    async def kill_run(self, run_id: uuid.UUID) -> None:
        managed = self._processes.get(run_id)
        if managed is None:
            return
        self._kill_requested.add(run_id)
        await managed.terminate()

    async def reconcile_orphans(self) -> list[ExecutionRun]:
        running = await self._find_running_runs()
        orphans = [run for run in running if not self._is_run_alive(run)]
        for run in orphans:
            await self._mark_run_failed(run)
        return orphans

    async def _find_running_runs(self) -> list[ExecutionRun]:
        result = await self.db.execute(select(ExecutionRun).where(ExecutionRun.status == RunStatus.RUNNING))
        return list(result.scalars())

    def _is_run_alive(self, run: ExecutionRun) -> bool:
        return run.pid is not None and process.is_pid_alive(run.pid)

    async def _mark_run_failed(self, run: ExecutionRun) -> None:
        run.status = RunStatus.FAILED
        run.completed_at = utcnow()
        self.db.add(self._build_orphan_attention_event(run))
        await self.commit()

    def _build_orphan_attention_event(self, run: ExecutionRun) -> AttentionEvent:
        return AttentionEvent(
            id=uuid.uuid4(),
            type=AttentionType.TASK_FAILED,
            title="Execution run orphaned",
            message=f"Run {run.id} had no live process on startup and was marked failed.",
        )

    async def commit(self) -> None:
        """Every db write goes through here, even from outside this class: one AsyncSession is shared across concurrent tasks, and it cannot survive two commits interleaving."""
        async with self._db_lock:
            await self.db.commit()


def require_resumable_session(agent: Agent, task_worktree: TaskWorktree, agent_session: AgentSession) -> None:
    if agent_session.agent_id != agent.id or agent_session.task_worktree_id != task_worktree.id:
        raise ValueError("agent_session does not belong to this agent and task worktree")
    if not agent_session.claude_session_id:
        raise ValueError("cannot resume a session with no persisted claude_session_id")
