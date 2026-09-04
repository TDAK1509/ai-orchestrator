import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import GUID, Base, TimestampMixin, UUIDPrimaryKeyMixin


class MeetingStatus(str, enum.Enum):
    ACTIVE = "active"
    ENDED = "ended"


class MeetingLoopState(str, enum.Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"


DEFAULT_MAX_ROUNDS = 3


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

    # allow-comment: C3 -- the facilitator loop's own state, distinct from status: a meeting is ACTIVE for its whole life but paused/running/idle turn by turn.
    facilitator_instructions: Mapped[str | None] = mapped_column(String, nullable=True)
    max_rounds: Mapped[int] = mapped_column(Integer, default=DEFAULT_MAX_ROUNDS, server_default=text(str(DEFAULT_MAX_ROUNDS)), nullable=False)
    chair_agent_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("agents.id"), nullable=True)
    current_round: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)
    next_speaker_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("agents.id"), nullable=True)
    loop_state: Mapped[MeetingLoopState] = mapped_column(
        Enum(MeetingLoopState, native_enum=False, length=10), default=MeetingLoopState.IDLE, server_default=text("'idle'"), nullable=False
    )


class MeetingAuthor(str, enum.Enum):
    HUMAN = "human"
    AGENT = "agent"
    # allow-comment: every row written before C3 was typed by a human impersonating an agent; backfilling it as AGENT would be a lie, and HUMAN doesn't distinguish it from a real human turn either.
    LEGACY_HUMAN_AS_AGENT = "legacy_human_as_agent"


class MeetingMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "meeting_messages"

    meeting_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("meetings.id"), nullable=False, index=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("agents.id"), nullable=True)
    content: Mapped[str] = mapped_column(String, nullable=False)
    author: Mapped[MeetingAuthor] = mapped_column(
        Enum(MeetingAuthor, native_enum=False, length=30),
        default=MeetingAuthor.LEGACY_HUMAN_AS_AGENT,
        server_default=text("'legacy_human_as_agent'"),
        nullable=False,
    )


class MeetingParticipant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Who was invited is recorded here, independent of where an agent's room_id points right now (an agent can be moved into a later meeting without erasing this one's roster)."""

    __tablename__ = "meeting_participants"
    __table_args__ = (UniqueConstraint("meeting_id", "agent_id", name="uq_meeting_participants_meeting_agent"),)

    meeting_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("meetings.id"), nullable=False, index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("agents.id"), nullable=False)
    round_robin_position: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)


class MeetingTurnState(str, enum.Enum):
    PROMPTED = "prompted"
    STREAMED = "streamed"
    COMMITTED = "committed"


class MeetingTurn(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """C3.4: a crash between sending a prompt and committing the message must resend or resume the turn, never silently lose or duplicate it."""

    __tablename__ = "meeting_turns"

    meeting_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("meetings.id"), nullable=False, index=True)
    round: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("agents.id"), nullable=False)
    state: Mapped[MeetingTurnState] = mapped_column(Enum(MeetingTurnState, native_enum=False, length=10), nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("execution_runs.id"), nullable=True)
    message_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("meeting_messages.id"), nullable=True)
