import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentStatus(str, enum.Enum):
    IDLE = "idle"
    QUEUED = "queued"
    WORKING = "working"
    BLOCKED = "blocked"


class Agent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agents"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(120), nullable=False)
    instructions: Mapped[str] = mapped_column(String, nullable=False, default="")

    status: Mapped[AgentStatus] = mapped_column(
        Enum(AgentStatus, native_enum=False, length=20),
        default=AgentStatus.IDLE,
        nullable=False,
    )
    needs_attention: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # allow-comment: separate from status (README Rule 2): an agent can be WORKING while in a meeting room, never a combined "in_meeting" status.
    room_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("rooms.id"), nullable=True, index=True)

    # allow-comment: a real FK here would be circular (Task/AgentSession already FK agents.id); service layer enforces it instead.
    current_task_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    current_agent_session_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
