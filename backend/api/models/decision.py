import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class DecisionStatus(str, enum.Enum):
    PENDING = "pending"
    ANSWERED = "answered"


class DecisionRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "decision_requests"

    agent_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("agents.id"), nullable=False)
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("tasks.id"), nullable=True
    )

    question: Mapped[str] = mapped_column(String, nullable=False)
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    allow_custom_answer: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    status: Mapped[DecisionStatus] = mapped_column(
        Enum(DecisionStatus, native_enum=False, length=10),
        default=DecisionStatus.PENDING,
        nullable=False,
    )
    answer: Mapped[str | None] = mapped_column(String, nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
