import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class MeetingStatus(str, enum.Enum):
    ACTIVE = "active"
    ENDED = "ended"


class Meeting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The outcome fields are populated once, at meeting end (README section 7), the same "agent produces its own structured record" pattern as AgentCheckpoint."""

    __tablename__ = "meetings"

    room_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("rooms.id"), nullable=False, unique=True)
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    goal: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[MeetingStatus] = mapped_column(
        Enum(MeetingStatus, native_enum=False, length=10), default=MeetingStatus.ACTIVE, nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    summary: Mapped[str | None] = mapped_column(String, nullable=True)
    decisions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    action_items: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    unresolved_questions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class MeetingMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "meeting_messages"

    meeting_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("meetings.id"), nullable=False, index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("agents.id"), nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)


class MeetingParticipant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Who was invited is recorded here, independent of where an agent's room_id points right now (an agent can be moved into a later meeting without erasing this one's roster)."""

    __tablename__ = "meeting_participants"
    __table_args__ = (UniqueConstraint("meeting_id", "agent_id", name="uq_meeting_participants_meeting_agent"),)

    meeting_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("meetings.id"), nullable=False, index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("agents.id"), nullable=False)
