import os
import sys
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db import DEFAULT_DATABASE_URL
from db import commit as db_commit
from models.agent import Agent
from models.base import utcnow
from models.session import AgentSession, BoundVia, ExecutionRun, RunStatus
from models.worktree import TaskWorktree

from . import process, worktree
from .mcp_config import McpServerRef, remove_mcp_config, write_mcp_config
from .prompt import build_follow_up_message
from .stream_parser import DomainEvent, parse_stream_line

TERMINAL_RUN_STATUSES = (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.KILLED, RunStatus.INTERRUPTED)
PROGRESS_FLUSH_SECONDS = 10.0


@dataclass
class RuntimeSettings:
    claude_binary: str = "claude"
    model: str = "claude-sonnet-5"
    permission_mode: str = "acceptEdits"
    runtime_root: Path = field(default_factory=lambda: Path(".agent-office/runtime"))
    database_url: str | None = field(default_factory=lambda: os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))
    # allow-comment: separate from database_url so a deployment can hand the agent-facing ask_human server a least-privilege role instead of the backend's own full-access connection string.
    ask_human_database_url: str | None = None


class RuntimeService:
    """The only service that touches OS processes and long-lived git state."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], settings: RuntimeSettings):
        # allow-comment: no bound self.db. spawn/resume/stream_events/reconcile_orphans each open their own session, since spawn and stream_events run in genuinely concurrent asyncio tasks (one background worker per run) and a single shared AsyncSession cannot be touched from two tasks at once.
        self.session_factory = session_factory
        self.settings = settings
        self._processes: dict[uuid.UUID, process.OwnedProcess] = {}
        self._last_progress_flush: dict[uuid.UUID, float] = {}
        self._result_outcome: dict[uuid.UUID, str | None] = {}

    async def spawn(
        self,
        agent: Agent,
        task_worktree: TaskWorktree,
        allowed_servers: list[McpServerRef],
        initial_message: dict,
        env: dict[str, str] | None = None,
    ) -> ExecutionRun:
        async with self.session_factory() as db:
            return await self._start_run(db, agent, task_worktree, allowed_servers, None, initial_message, env)

    async def resume(self, agent: Agent, agent_session: AgentSession, task_worktree: TaskWorktree, allowed_servers: list[McpServerRef], prompt_text: str, env: dict[str, str] | None = None) -> ExecutionRun:
        require_resumable_session(agent, task_worktree, agent_session)
        message = build_follow_up_message(prompt_text)
        async with self.session_factory() as db:
            return await self._start_run(db, agent, task_worktree, allowed_servers, agent_session, message, env)

    async def _start_run(self, db, agent, task_worktree, allowed_servers, resume_session, initial_message, env) -> ExecutionRun:
        agent_session, run = await self._open_session_and_run(db, agent, task_worktree, resume_session)
        internal_servers = self._build_internal_servers(agent, task_worktree, agent_session)
        mcp_config_path = write_mcp_config(self._agent_runtime_dir(agent.id), allowed_servers, internal_servers)
        await self._launch_process(db, agent_session, run, task_worktree, mcp_config_path, resume_session, initial_message, env)
        return run

    def _build_internal_servers(self, agent: Agent, task_worktree: TaskWorktree, agent_session: AgentSession) -> dict[str, dict]:
        """Wires ask_human (19.7) and checkpoint (17.5) in for every run: unlike a catalog server, neither is opt-in."""
        database_url = self.settings.ask_human_database_url or self.settings.database_url
        if not database_url:
            return {}
        env = {
            "DATABASE_URL": database_url,
            "AGENT_ID": str(agent.id),
            "TASK_ID": str(task_worktree.task_id),
            "AGENT_SESSION_ID": str(agent_session.id),
        }
        return self._internal_server_entries(env)

    def _internal_server_entries(self, env: dict[str, str]) -> dict[str, dict]:
        scripts = {"ask_human": "ask_human_mcp.py", "checkpoint": "checkpoint_mcp.py"}
        return {
            name: {"command": sys.executable, "args": [str(Path(__file__).with_name(script))], "env": env}
            for name, script in scripts.items()
        }

    async def _open_session_and_run(
        self, db, agent, task_worktree, resume_session: AgentSession | None
    ) -> tuple[AgentSession, ExecutionRun]:
        before_commit = await worktree.read_head_commit(Path(task_worktree.path))
        agent_session = resume_session or self._open_agent_session(db, agent, task_worktree)
        bound_via = BoundVia.RESUME if resume_session else BoundVia.SPAWN
        run = self._open_execution_run(db, agent_session, bound_via, before_commit)
        return agent_session, run

    async def _launch_process(self, db, agent_session, run, task_worktree, mcp_config_path, resume_session, initial_message, env) -> None:
        managed = await self._spawn_process(agent_session.agent_id, run.id, task_worktree, mcp_config_path, resume_session, env)
        run.pid = managed.pid
        agent_session.approx_chars += len(str(initial_message))
        await db_commit(db)
        self._processes[run.id] = managed
        await managed.send_line(initial_message)
        await managed.close_stdin()

    def _agent_runtime_dir(self, agent_id: uuid.UUID) -> Path:
        return self.settings.runtime_root / str(agent_id)

    def _open_agent_session(self, db, agent, task_worktree) -> AgentSession:
        # allow-comment: approx_chars set explicitly, not left to the model's default=0: that's a Python-side ORM default and doesn't populate until this object is flushed, and _launch_process reads it before any flush happens.
        session = AgentSession(
            id=uuid.uuid4(), agent_id=agent.id, task_worktree_id=task_worktree.id, cwd=task_worktree.path, approx_chars=0
        )
        db.add(session)
        return session

    def _open_execution_run(self, db, agent_session: AgentSession, bound_via: BoundVia, before_commit: str) -> ExecutionRun:
        run = ExecutionRun(
            id=uuid.uuid4(),
            agent_session_id=agent_session.id,
            bound_via=bound_via,
            before_head_commit=before_commit,
            started_at=utcnow(),
        )
        db.add(run)
        return run

    async def _spawn_process(
        self, agent_id: uuid.UUID, run_id: uuid.UUID, task_worktree, mcp_config_path: Path, resume_session: AgentSession | None, env: dict[str, str] | None
    ) -> process.OwnedProcess:
        command = self._build_command(mcp_config_path, resume_session)
        run_directory = self._run_dir(agent_id, run_id)
        return await process.spawn(command, cwd=Path(task_worktree.path), run_directory=run_directory, env=env)

    def _run_dir(self, agent_id: uuid.UUID, run_id: uuid.UUID) -> Path:
        return process.run_dir(self.settings.runtime_root, agent_id, run_id)

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
        """Owns one session for the run's whole life (README 31.1): this is the one worker allowed to write these rows, and it never shares that session with spawn() or another run's stream."""
        async with self.session_factory() as db:
            agent_session, run = await self._load_session_and_run(db, run_id)
            managed = self.resolve_process(agent_session.agent_id, run)
            try:
                async for line, offset in managed.iter_stdout_lines(run.stdout_offset):
                    yield await self._apply_line(db, agent_session, run, line, offset)
            finally:
                await self._finalize_run(db, managed, agent_session, run)

    def resolve_process(self, agent_id: uuid.UUID, run: ExecutionRun) -> process.OwnedProcess | process.AdoptedProcess:
        """Phase 0.3: an in-process run still has its live asyncio handle; a run this backend never spawned (adopted after a restart) is reattached from the files its supervisor wrote."""
        owned = self._processes.get(run.id)
        return owned if owned is not None else process.AdoptedProcess(self._run_dir(agent_id, run.id))

    async def _load_session_and_run(self, db, run_id: uuid.UUID) -> tuple[AgentSession, ExecutionRun]:
        run = await db.get(ExecutionRun, run_id)
        agent_session = await db.get(AgentSession, run.agent_session_id)
        return agent_session, run

    async def _apply_line(self, db, agent_session: AgentSession, run: ExecutionRun, line: str, offset: int) -> DomainEvent:
        track_context_usage(agent_session, line)
        run.stdout_offset = offset
        run.last_event_at = utcnow()
        event = parse_stream_line(line)
        await self._apply_event(db, agent_session, event)
        self._remember_result_outcome(run.id, event)
        await self._flush_progress_if_due(db, run)
        return event

    def _remember_result_outcome(self, run_id: uuid.UUID, event: DomainEvent) -> None:
        if event.kind == "run_finished":
            self._result_outcome[run_id] = event.exit_result

    async def _apply_event(self, db, agent_session: AgentSession, event: DomainEvent) -> None:
        if event.kind == "session_started" and event.claude_session_id:
            agent_session.claude_session_id = event.claude_session_id
            await db_commit(db)

    async def _flush_progress_if_due(self, db, run: ExecutionRun) -> None:
        """Persists stdout_offset so a reattach resumes past applied output (Phase 0.3), throttled so a commit isn't serialized on db.COMMIT_LOCK for every single line."""
        now = time.monotonic()
        if now - self._last_progress_flush.get(run.id, 0.0) < PROGRESS_FLUSH_SECONDS:
            return
        self._last_progress_flush[run.id] = now
        await db_commit(db)

    async def _finalize_run(self, db, managed: process.OwnedProcess | process.AdoptedProcess, agent_session: AgentSession, run: ExecutionRun) -> None:
        # allow-comment: a caller stopping early (disconnect, cancellation, explicit kill) must still stop the process and record a status; for a run already finished when this loop started, terminate()/wait() are harmless no-ops.
        await managed.terminate()
        exit_code = await managed.wait()
        run.exit_code = exit_code
        run.completed_at = utcnow()
        run.status = await self._resolve_final_status(db, run, exit_code, self._result_outcome.pop(run.id, None))
        run.after_head_commit = await worktree.read_head_commit(Path(agent_session.cwd))
        self._processes.pop(run.id, None)
        self._last_progress_flush.pop(run.id, None)
        remove_mcp_config(self._agent_runtime_dir(agent_session.agent_id))
        await db_commit(db)

    async def _resolve_final_status(self, db, run: ExecutionRun, exit_code: int | None, result_outcome: str | None) -> RunStatus:
        if await self._was_kill_requested(db, run.id):
            return RunStatus.KILLED
        if exit_code is not None:
            return RunStatus.COMPLETED if exit_code == 0 else RunStatus.FAILED
        if result_outcome is not None:
            return RunStatus.COMPLETED if result_outcome == "success" else RunStatus.FAILED
        # allow-comment: the process is gone, exit.json was never written and no result event was seen -- the backend cannot know whether the work landed, so this is neither success nor failure but an open question for Track B to resume or resolve.
        return RunStatus.INTERRUPTED

    async def _was_kill_requested(self, db, run_id: uuid.UUID) -> bool:
        result = await db.execute(select(ExecutionRun.kill_requested).where(ExecutionRun.id == run_id))
        return bool(result.scalar_one())

    async def kill_run(self, run_id: uuid.UUID) -> None:
        await self._mark_kill_requested(run_id)
        managed = self._processes.get(run_id)
        if managed is not None:
            await managed.terminate()

    async def _mark_kill_requested(self, run_id: uuid.UUID) -> None:
        async with self.session_factory() as db:
            run = await db.get(ExecutionRun, run_id)
            run.kill_requested = True
            await db_commit(db)

def require_resumable_session(agent: Agent, task_worktree: TaskWorktree, agent_session: AgentSession) -> None:
    if agent_session.agent_id != agent.id or agent_session.task_worktree_id != task_worktree.id:
        raise ValueError("agent_session does not belong to this agent and task worktree")
    if not agent_session.claude_session_id:
        raise ValueError("cannot resume a session with no persisted claude_session_id")


def track_context_usage(agent_session: AgentSession, line: str) -> None:
    """Raw wire size, not a real token count (no tokenizer here): just enough of a proxy for README 17.5's "track approximate context usage" for a human or future job to act on."""
    agent_session.approx_chars += len(line)
