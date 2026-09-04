import uuid

from sqlalchemy import select

from db import commit
from models.agent import Agent
from models.base import utcnow
from models.meeting import Meeting, MeetingMessage, MeetingParticipant, MeetingStatus
from models.memory import MemoryScope, MemorySourceType, MemoryType
from models.room import Room, RoomType
from services.memory_service import build_memory
from services.room_service import place_agent_in_room


async def create_meeting(db, topic: str, goal: str | None, participants: list[Agent]) -> Meeting:
    """Participants move into a fresh room for the meeting's whole life; everyone else stays exactly where they were (README section 7). One commit: a mid-loop failure must never leave the room half-populated."""
    room = Room(id=uuid.uuid4(), name=topic, type=RoomType.MEETING)
    db.add(room)
    meeting = Meeting(id=uuid.uuid4(), room_id=room.id, topic=topic, goal=goal)
    db.add(meeting)
    for agent in participants:
        db.add(MeetingParticipant(id=uuid.uuid4(), meeting_id=meeting.id, agent_id=agent.id))
        place_agent_in_room(agent, room)
    await commit(db)
    return meeting


async def add_meeting_message(db, meeting: Meeting, agent: Agent, content: str) -> MeetingMessage:
    require_active_meeting(meeting)
    await require_meeting_participant(db, meeting, agent)
    message = MeetingMessage(id=uuid.uuid4(), meeting_id=meeting.id, agent_id=agent.id, content=content)
    db.add(message)
    await commit(db)
    return message


async def require_meeting_participant(db, meeting: Meeting, agent: Agent) -> None:
    if not agent.active:
        raise ValueError(f"agent {agent.id} is not active")
    participant_ids = await list_meeting_participant_ids(db, meeting.id)
    if agent.id not in participant_ids:
        raise ValueError(f"agent {agent.id} is not a participant of meeting {meeting.id}")


async def list_meeting_participant_ids(db, meeting_id: uuid.UUID) -> set[uuid.UUID]:
    query = select(MeetingParticipant.agent_id).where(MeetingParticipant.meeting_id == meeting_id)
    return set((await db.execute(query)).scalars())


async def list_meeting_messages(db, meeting_id: uuid.UUID) -> list[MeetingMessage]:
    query = select(MeetingMessage).where(MeetingMessage.meeting_id == meeting_id).order_by(MeetingMessage.created_at)
    return list((await db.execute(query)).scalars())


async def end_meeting(db, meeting: Meeting, main_room: Room, summary: str, decisions: list[str] | None = None, action_items: list[str] | None = None, unresolved_questions: list[str] | None = None) -> Meeting:
    """Only the transcript is agent-written; the outcome fields are, same as a checkpoint, structured data the app can extract into memory with no model pass (README section 7 + 32.2)."""
    require_active_meeting(meeting)
    close_meeting(meeting, summary, decisions, action_items, unresolved_questions)
    await return_participants_to_main_room(db, meeting, main_room)
    await extract_memories_from_meeting(db, meeting)
    await commit(db)
    return meeting


def close_meeting(meeting: Meeting, summary: str, decisions: list[str] | None, action_items: list[str] | None, unresolved_questions: list[str] | None) -> None:
    meeting.status = MeetingStatus.ENDED
    meeting.ended_at = utcnow()
    meeting.summary = summary
    meeting.decisions = decisions or []
    meeting.action_items = action_items or []
    meeting.unresolved_questions = unresolved_questions or []


async def return_participants_to_main_room(db, meeting: Meeting, main_room: Room) -> None:
    """The recorded roster, not whoever currently occupies the meeting room: an agent pulled into a later meeting must still be sent home from this one."""
    for agent in await list_meeting_participants(db, meeting.id):
        if agent.room_id == meeting.room_id:
            agent.room_id = main_room.id


async def list_meeting_participants(db, meeting_id: uuid.UUID) -> list[Agent]:
    query = (
        select(Agent)
        .join(MeetingParticipant, MeetingParticipant.agent_id == Agent.id)
        .where(MeetingParticipant.meeting_id == meeting_id)
    )
    return list((await db.execute(query)).scalars())


async def extract_memories_from_meeting(db, meeting: Meeting) -> list:
    typed_fields = [(meeting.decisions, MemoryType.DECISION), (meeting.action_items, MemoryType.TASK_SUMMARY)]
    records = [build_meeting_memory(meeting, content, type_) for values, type_ in typed_fields for content in values]
    for record in records:
        db.add(record)
    return records


def build_meeting_memory(meeting: Meeting, content: str, type_: MemoryType):
    return build_memory(
        MemoryScope.WORKSPACE, content, type_, None, None,
        importance=0.5, pinned=False, source_type=MemorySourceType.MEETING, source_id=str(meeting.id),
    )


def require_active_meeting(meeting: Meeting) -> None:
    if meeting.status != MeetingStatus.ACTIVE:
        raise ValueError(f"meeting {meeting.id} is not active (status={meeting.status.value})")
