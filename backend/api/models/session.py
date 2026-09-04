import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A Claude Code conversation. Spans one or more ExecutionRuns via --resume."""

    __tablename__ = "agent_sessions"

    agent_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("agents.id"), nullable=False)
    task_worktree_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("task_worktrees.id"), nullable=False
    )
    claude_session_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cwd: Mapped[str] = mapped_column(String(500), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # allow-comment: a character count is a proxy for context usage, not real token counting, which needs a tokenizer this repo doesn't have (README 17.5 "track approximate context usage"). server_default, not just default=0: a NOT NULL column added to a table that may already have rows needs a value the database itself can supply during the ALTER, not just one the ORM supplies for new inserts.
    approx_chars: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)

    # allow-comment: Track B2's durable resume intent -- Agent.status=QUEUED can't express "resume this exact conversation, don't spawn a fresh one", so it lives here instead.
    resume_pending: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"), nullable=False)
    resume_prompt: Mapped[str | None] = mapped_column(String, nullable=True)
    resume_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)
    resume_claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BoundVia(str, enum.Enum):
    SPAWN = "spawn"
    RESUME = "resume"
    MANUAL = "manual"


class RunStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"
    INTERRUPTED = "interrupted"


class ExecutionRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One OS process invocation against an AgentSession."""

    __tablename__ = "execution_runs"

    agent_session_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("agent_sessions.id"), nullable=False
    )
    bound_via: Mapped[BoundVia] = mapped_column(
        Enum(BoundVia, native_enum=False, length=10), nullable=False
    )
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, native_enum=False, length=20),
        default=RunStatus.RUNNING,
        nullable=False,
    )
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # allow-comment: a deliberate kill (Phase 0.4) must survive a crash between the signal and finalization, so it is a durable column, not the in-memory set this replaces.
    kill_requested: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"), nullable=False)
    # allow-comment: bytes of stdout.jsonl already applied to domain state (Phase 0.3), so a reattach after a restart resumes past this point instead of replaying it.
    stdout_offset: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)
    # allow-comment: Track B3's hang signal -- silence here does not by itself mean stuck, since ask_human's wait_for_answer legitimately produces none while waiting on a human.
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    before_head_commit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    after_head_commit: Mapped[str | None] = mapped_column(String(64), nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
