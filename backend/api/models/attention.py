import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class AttentionType(str, enum.Enum):
    DECISION_REQUIRED = "decision_required"
    PERMISSION_REQUIRED = "permission_required"
    AGENT_BLOCKED = "agent_blocked"
    TASK_FAILED = "task_failed"
    AGENT_QUESTION = "agent_question"


class AttentionEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attention_events"

    type: Mapped[AttentionType] = mapped_column(
        Enum(AttentionType, native_enum=False, length=30), nullable=False
    )

    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("agents.id"), nullable=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("tasks.id"), nullable=True
    )
    decision_request_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("decision_requests.id"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)

    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
