import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
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


class BoundVia(str, enum.Enum):
    SPAWN = "spawn"
    RESUME = "resume"
    MANUAL = "manual"


class RunStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"


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
        Enum(RunStatus, native_enum=False, length=10),
        default=RunStatus.RUNNING,
        nullable=False,
    )
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    before_head_commit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    after_head_commit: Mapped[str | None] = mapped_column(String(64), nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
