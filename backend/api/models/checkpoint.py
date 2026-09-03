import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentCheckpoint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Structured, not summarized by us (README 32.2): the agent itself produces these fields via the checkpoint tool, so extracting them into memory needs no model pass."""

    __tablename__ = "agent_checkpoints"

    agent_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("agents.id"), nullable=False)
    task_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("tasks.id"), nullable=True)
    agent_session_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("agent_sessions.id"), nullable=False)

    summary: Mapped[str] = mapped_column(String, nullable=False)
    decisions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    discoveries: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    important_files: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    unfinished_work: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    blockers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    risks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    branch: Mapped[str | None] = mapped_column(String(200), nullable=True)
    head_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    test_status: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # allow-comment: set once rotation actually consumes this checkpoint, so a retry of the same rotation can't re-extract its memories or spawn a second replacement session.
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
