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
from models.meeting import Meeting
from models.session import AgentSession, BoundVia, ExecutionRun, RunStatus
from models.worktree import TaskWorktree

from . import process, worktree
from .mcp_config import McpServerRef, remove_mcp_config, write_mcp_config
from .prompt import build_follow_up_message
from .stream_parser import DomainEvent, parse_stream_line

PROGRESS_FLUSH_SECONDS = 10.0


@dataclass
class RuntimeSettings:
    claude_binary: str = "claude"
    model: str = "claude-sonnet-5"
    effort: str | None = None
    permission_mode: str = "acceptEdits"
    runtime_root: Path = field(default_factory=lambda: Path(".agent-office/runtime"))
    database_url: str | None = field(default_factory=lambda: os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))
    # allow-comment: separate from database_url so a deployment can hand the agent-facing ask_human server a least-privilege role instead of the backend's own full-access connection string.
    ask_human_database_url: str | None = None


@dataclass(frozen=True)
class AgentRuntimePolicy:
    """README 19.8: per-agent model and effort, resolved once at spawn -- a pinned agent overrides the workspace default, a NULL one follows it."""

    model: str
    effort: str | None


def resolve_runtime_policy(agent: Agent, settings: RuntimeSettings) -> AgentRuntimePolicy:
    effort = agent.effort.value if agent.effort else settings.effort
    return AgentRuntimePolicy(model=agent.model or settings.model, effort=effort)


@dataclass
class RunTarget:
    """C4: what a session runs against -- a task worktree (with a commit history to read) or a meeting (a plain cwd, no commits)."""

    cwd: Path
    task_worktree: TaskWorktree | None = None
    meeting: Meeting | None = None

    @property
    def task_id(self) -> uuid.UUID | None:
        return self.task_worktree.task_id if self.task_worktree else None


class RuntimeService:
    """The only service that touches OS processes and long-lived git state."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], settings: RuntimeSettings):
        # allow-comment: no bound self.db. spawn/resume/stream_events/reconcile_orphans each open their own session, since spawn and stream_events run in genuinely concurrent asyncio tasks (one background worker per run) and a single shared AsyncSession cannot be touched from two tasks at once.
        self.session_factory = session_factory
        self.settings = settings
        self._processes: dict[uuid.UUID, process.OwnedProcess] = {}
        self._last_progress_flush: dict[uuid.UUID, float] = {}
        self._result_outcome: dict[uuid.UUID, str | None] = {}
        self._detached: set[uuid.UUID] = set()

    async def spawn(
        self,
        agent: Agent,
        task_worktree: TaskWorktree,
        allowed_servers: list[McpServerRef],
        initial_message: dict,
        env: dict[str, str] | None = None,
    ) -> ExecutionRun:
        target = RunTarget(cwd=Path(task_worktree.path), task_worktree=task_worktree)
        async with self.session_factory() as db:
            return await self._start_run(db, agent, target, allowed_servers, None, initial_message, env, keep_stdin_open=False)

    async def resume(self, agent: Agent, agent_session: AgentSession, task_worktree: TaskWorktree, allowed_servers: list[McpServerRef], prompt_text: str, env: dict[str, str] | None = None) -> ExecutionRun:
        require_resumable_session(agent, agent_session, task_worktree)
        target = RunTarget(cwd=Path(task_worktree.path), task_worktree=task_worktree)
        message = build_follow_up_message(prompt_text)
        async with self.session_factory() as db:
            return await self._start_run(db, agent, target, allowed_servers, agent_session, message, env, keep_stdin_open=False)

    async def spawn_meeting_turn(self, agent: Agent, meeting: Meeting, cwd: Path, allowed_servers: list[McpServerRef], initial_message: dict, env: dict[str, str] | None = None) -> ExecutionRun:
        """C5: the first turn for a participant -- a long-lived process (keep_stdin_open) with no task worktree."""
        target = RunTarget(cwd=cwd, meeting=meeting)
        async with self.session_factory() as db:
            return await self._start_run(db, agent, target, allowed_servers, None, initial_message, env, keep_stdin_open=True)

    async def resume_meeting_turn(self, agent: Agent, agent_session: AgentSession, cwd: Path, allowed_servers: list[McpServerRef], prompt_text: str, env: dict[str, str] | None = None) -> ExecutionRun:
        """C5: re-spawn after a restart terminated the previous long-lived process -- the conversation itself survives via --resume."""
        require_resumable_session(agent, agent_session, None)
        target = RunTarget(cwd=cwd)
        message = build_follow_up_message(prompt_text)
        async with self.session_factory() as db:
            return await self._start_run(db, agent, target, allowed_servers, agent_session, message, env, keep_stdin_open=True)

    async def send_message(self, run_id: uuid.UUID, payload: dict) -> None:
        """C5: a later turn on an already-open, long-lived process -- no new run, just another line on the same stdin."""
        managed = self._processes.get(run_id)
        if managed is None:
            raise RuntimeError(f"run {run_id} has no live process to send to")
        await managed.send_line(payload)

    async def _start_run(self, db, agent, target: RunTarget, allowed_servers, resume_session, initial_message, env, keep_stdin_open) -> ExecutionRun:
        policy = resolve_runtime_policy(agent, self.settings)
        agent_session, run = await self._open_session_and_run(db, agent, target, resume_session)
        internal_servers = self._build_internal_servers(agent, target, agent_session)
        mcp_config_path = write_mcp_config(self._run_dir(agent.id, run.id), allowed_servers, internal_servers)
        await self._launch_process(db, agent_session, run, target, mcp_config_path, resume_session, initial_message, env, keep_stdin_open, policy)
        return run

    def _build_internal_servers(self, agent: Agent, target: RunTarget, agent_session: AgentSession) -> dict[str, dict]:
        """Wires ask_human (19.7) and checkpoint (17.5) in for every run: unlike a catalog server, neither is opt-in."""
        database_url = self.settings.ask_human_database_url or self.settings.database_url
        if not database_url:
            return {}
        env = {"DATABASE_URL": database_url, "AGENT_ID": str(agent.id), "AGENT_SESSION_ID": str(agent_session.id)}
        if target.task_id is not None:
            env["TASK_ID"] = str(target.task_id)
        return self._internal_server_entries(env)

    def _internal_server_entries(self, env: dict[str, str]) -> dict[str, dict]:
        scripts = {"ask_human": "ask_human_mcp.py", "checkpoint": "checkpoint_mcp.py"}
        return {
            name: {"command": sys.executable, "args": [str(Path(__file__).with_name(script))], "env": env}
            for name, script in scripts.items()
        }

    async def _open_session_and_run(
        self, db, agent, target: RunTarget, resume_session: AgentSession | None
    ) -> tuple[AgentSession, ExecutionRun]:
        before_commit = await self._read_head_commit(target)
        agent_session = resume_session or self._open_agent_session(db, agent, target)
        bound_via = BoundVia.RESUME if resume_session else BoundVia.SPAWN
        run = self._open_execution_run(db, agent_session, bound_via, before_commit)
        return agent_session, run

    async def _read_head_commit(self, target: RunTarget) -> str | None:
        """C4: a meeting has no commit history to read -- HEAD in repo_root would belong to whatever task last landed there, not to this session."""
        return await worktree.read_head_commit(target.cwd) if target.task_worktree else None

    async def _launch_process(self, db, agent_session, run, target: RunTarget, mcp_config_path, resume_session, initial_message, env, keep_stdin_open, policy: AgentRuntimePolicy) -> None:
        managed = await self._spawn_process(agent_session.agent_id, run.id, target, mcp_config_path, resume_session, env, policy)
        run.pid = managed.pid
        agent_session.approx_chars += len(str(initial_message))
        await db_commit(db)
        self._processes[run.id] = managed
        await managed.send_line(initial_message)
        if not keep_stdin_open:
            await managed.close_stdin()

    def _open_agent_session(self, db, agent, target: RunTarget) -> AgentSession:
        # allow-comment: approx_chars set explicitly, not left to the model's default=0: that's a Python-side ORM default and doesn't populate until this object is flushed, and _launch_process reads it before any flush happens.
        session = AgentSession(
            id=uuid.uuid4(), agent_id=agent.id,
            task_worktree_id=target.task_worktree.id if target.task_worktree else None,
            meeting_id=target.meeting.id if target.meeting else None,
            cwd=str(target.cwd), approx_chars=0,
        )
        db.add(session)
        return session

    def _open_execution_run(self, db, agent_session: AgentSession, bound_via: BoundVia, before_commit: str | None) -> ExecutionRun:
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
        self, agent_id: uuid.UUID, run_id: uuid.UUID, target: RunTarget, mcp_config_path: Path, resume_session: AgentSession | None, env: dict[str, str] | None, policy: AgentRuntimePolicy
    ) -> process.OwnedProcess:
        command = self._build_command(mcp_config_path, resume_session, target, policy)
        run_directory = self._run_dir(agent_id, run_id)
        return await process.spawn(command, cwd=target.cwd, run_directory=run_directory, env=env)

    def _run_dir(self, agent_id: uuid.UUID, run_id: uuid.UUID) -> Path:
        return process.run_dir(self.settings.runtime_root, agent_id, run_id)

    def _build_command(self, mcp_config_path: Path, resume_session: AgentSession | None, target: RunTarget, policy: AgentRuntimePolicy) -> list[str]:
        command = self._base_command_args(mcp_config_path, target, policy)
        if resume_session and resume_session.claude_session_id:
            command += ["--resume", resume_session.claude_session_id]
        return command

    def _base_command_args(self, mcp_config_path: Path, target: RunTarget, policy: AgentRuntimePolicy) -> list[str]:
        return self._streaming_flags() + self._session_flags(mcp_config_path, target, policy)

    def _streaming_flags(self) -> list[str]:
        return [
            self.settings.claude_binary,
            "--print",
            "--output-format", "stream-json",
            "--input-format", "stream-json",
            "--include-partial-messages",
            "--verbose",
        ]

    def _session_flags(self, mcp_config_path: Path, target: RunTarget, policy: AgentRuntimePolicy) -> list[str]:
        """C5: a meeting turn gets its own permission mode and an explicit tool disallow-list -- --disallowed-tools alone is not a boundary, since _build_internal_servers still injects MCP servers regardless, but it narrows the surface a catalog server's own tools could still reach."""
        flags = [
            "--model", policy.model,
            "--permission-mode", "plan" if target.meeting else self.settings.permission_mode,
            "--mcp-config", str(mcp_config_path),
            "--strict-mcp-config",
        ]
        if policy.effort:
            flags += ["--effort", policy.effort]
        return flags + (["--disallowed-tools", "Edit,Write,Bash"] if target.meeting else [])

    async def stream_events(self, run_id: uuid.UUID) -> AsyncIterator[DomainEvent]:
        """Owns one session for the run's whole life (README 31.1): this is the one worker allowed to write these rows, and it never shares that session with spawn() or another run's stream."""
        async with self.session_factory() as db:
            agent_session, run = await self._load_session_and_run(db, run_id)
            managed = self.resolve_process(agent_session.agent_id, run)
            try:
                async for line, offset in managed.iter_stdout_lines(run.stdout_offset):
                    yield await self._apply_line(db, agent_session, run, line, offset)
            finally:
                await self._finalize_unless_detached(db, managed, agent_session, run)

    async def _finalize_unless_detached(self, db, managed, agent_session, run: ExecutionRun) -> None:
        if run.id in self._detached:
            self._detached.discard(run.id)
        else:
            await self._finalize_run(db, managed, agent_session, run)

    def detach(self, run_id: uuid.UUID) -> None:
        """Phase 0.6: a graceful shutdown must not fail every in-flight task by killing its process -- detaching skips stream_events' finalize (and the terminate() inside it) entirely, leaving the supervisor and its child running so B1 can reattach them next startup, exactly as it does after a crash."""
        self._detached.add(run_id)

    async def read_turn_events(self, run_id: uuid.UUID) -> AsyncIterator[DomainEvent]:
        """C5: reads output for one meeting turn only, stopping at that turn's result event without finalizing the run -- the process stays alive for the next turn, unlike stream_events."""
        async with self.session_factory() as db:
            agent_session, run = await self._load_session_and_run(db, run_id)
            managed = self.resolve_process(agent_session.agent_id, run)
            async for line, offset in managed.iter_stdout_lines(run.stdout_offset):
                event = await self._apply_line(db, agent_session, run, line, offset)
                yield event
                if event.kind == "run_finished":
                    return

    async def finalize_meeting_run(self, run_id: uuid.UUID) -> None:
        """C5: a meeting turn's process is never driven through stream_events, so nothing else ever calls _finalize_run for it -- this is that call, made once the participant's process is actually done (meeting ended, stopped, or terminated for a restart)."""
        async with self.session_factory() as db:
            agent_session, run = await self._load_session_and_run(db, run_id)
            managed = self.resolve_process(agent_session.agent_id, run)
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
        if agent_session.task_worktree_id is not None:
            run.after_head_commit = await worktree.read_head_commit(Path(agent_session.cwd))
        self._processes.pop(run.id, None)
        self._last_progress_flush.pop(run.id, None)
        remove_mcp_config(self._run_dir(agent_session.agent_id, run.id))
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


def require_resumable_session(agent: Agent, agent_session: AgentSession, task_worktree: TaskWorktree | None) -> None:
    if agent_session.agent_id != agent.id:
        raise ValueError("agent_session does not belong to this agent")
    if task_worktree is not None and agent_session.task_worktree_id != task_worktree.id:
        raise ValueError("agent_session does not belong to this task worktree")
    if not agent_session.claude_session_id:
        raise ValueError("cannot resume a session with no persisted claude_session_id")


def track_context_usage(agent_session: AgentSession, line: str) -> None:
    """Raw wire size, not a real token count (no tokenizer here): just enough of a proxy for README 17.5's "track approximate context usage" for a human or future job to act on."""
    agent_session.approx_chars += len(line)
