import uuid
from pathlib import Path

from sqlalchemy import select, update

from db import commit
from events.bus import bus
from events.schema import (
    MEETING_CREATED,
    MEETING_ENDED,
    MEETING_MESSAGE,
    MEETING_UPDATED,
)
from models.agent import Agent
from models.base import utcnow
from models.meeting import (
    Meeting,
    MeetingAuthor,
    MeetingLoopState,
    MeetingMessage,
    MeetingParticipant,
    MeetingStatus,
    MeetingTurn,
    MeetingTurnState,
)
from models.memory import MemoryScope, MemorySourceType, MemoryType
from models.room import Room, RoomType
from runtime.runtime_service import RuntimeService
from serialization import serialize
from services.memory_service import build_memory
from services.room_service import place_agent_in_room
from services.scheduler_service import claim_participants_or_fail, release_participants
from services.task_service import TaskRuntimePolicy, promote_next_queued_agent


async def create_meeting(db, topic: str, goal: str | None, participants: list[Agent], policy: TaskRuntimePolicy, facilitator_instructions: str | None = None, max_rounds: int = 3, chair_agent_id: uuid.UUID | None = None) -> Meeting:
    """C1: every participant must be IDLE and claimed as a whole set, under the same slot lock task assignment uses -- no participant is ever left QUEUED, since promote_next_queued_agent assumes a queued agent has a task."""
    if not participants:
        raise ValueError("a meeting needs at least one participant")
    if not await claim_participants_or_fail(db, [agent.id for agent in participants], policy.max_concurrent_agents):
        raise ValueError("not every participant is idle, or there is not capacity for the whole meeting")
    meeting = await open_meeting_room(db, topic, goal, participants, facilitator_instructions, max_rounds, chair_agent_id)
    bus.publish(MEETING_CREATED, serialize(meeting))
    return meeting


async def open_meeting_room(db, topic, goal, participants, facilitator_instructions, max_rounds, chair_agent_id) -> Meeting:
    room = Room(id=uuid.uuid4(), name=topic, type=RoomType.MEETING)
    db.add(room)
    meeting = build_meeting(room.id, topic, goal, facilitator_instructions, max_rounds, chair_agent_id, participants)
    db.add(meeting)
    seat_participants(db, meeting, room, participants)
    await commit(db)
    return meeting


def build_meeting(room_id, topic, goal, facilitator_instructions, max_rounds, chair_agent_id, participants: list[Agent]) -> Meeting:
    return Meeting(
        id=uuid.uuid4(), room_id=room_id, topic=topic, goal=goal,
        facilitator_instructions=facilitator_instructions, max_rounds=max_rounds,
        chair_agent_id=chair_agent_id or participants[0].id,
        next_speaker_id=participants[0].id,
    )


def seat_participants(db, meeting: Meeting, room: Room, participants: list[Agent]) -> None:
    for position, agent in enumerate(participants):
        db.add(MeetingParticipant(id=uuid.uuid4(), meeting_id=meeting.id, agent_id=agent.id, round_robin_position=position))
        place_agent_in_room(agent, room)


async def add_human_message(db, meeting: Meeting, content: str) -> MeetingMessage:
    """A human interjection: not attributed to any participant, distinguishable from an agent's own turn (C3's author field)."""
    require_active_meeting(meeting)
    message = MeetingMessage(id=uuid.uuid4(), meeting_id=meeting.id, agent_id=None, content=content, author=MeetingAuthor.HUMAN)
    db.add(message)
    await commit(db)
    bus.publish(MEETING_MESSAGE, serialize(message))
    return message


async def list_meeting_messages(db, meeting_id: uuid.UUID) -> list[MeetingMessage]:
    query = select(MeetingMessage).where(MeetingMessage.meeting_id == meeting_id).order_by(MeetingMessage.created_at)
    return list((await db.execute(query)).scalars())


async def list_meetings(db) -> list[Meeting]:
    return list((await db.execute(select(Meeting).order_by(Meeting.created_at.desc()))).scalars())


async def end_meeting(db, runtime_service: RuntimeService, repo_root: Path, policy: TaskRuntimePolicy, meeting: Meeting, main_room: Room, summary: str, decisions: list[str] | None = None, action_items: list[str] | None = None, unresolved_questions: list[str] | None = None) -> Meeting:
    """C6: claims the row atomically (UPDATE ... WHERE status = ACTIVE) so a manual End Meeting racing the automatic close-out can't both extract memories and both release the same participants."""
    if not await claim_active_meeting(db, meeting.id):
        raise ValueError(f"meeting {meeting.id} is not active")
    participant_ids = await close_and_extract(db, meeting, main_room, summary, decisions, action_items, unresolved_questions)
    await release_participants(db, participant_ids)
    await promote_next_queued_agent(db, runtime_service, repo_root, policy)
    return meeting


async def claim_active_meeting(db, meeting_id: uuid.UUID) -> bool:
    stmt = update(Meeting).where(Meeting.id == meeting_id, Meeting.status == MeetingStatus.ACTIVE).values(status=MeetingStatus.ENDED)
    result = await db.execute(stmt)
    return result.rowcount > 0


async def close_and_extract(db, meeting: Meeting, main_room: Room, summary: str, decisions: list[str] | None, action_items: list[str] | None, unresolved_questions: list[str] | None) -> list[uuid.UUID]:
    participant_ids = [agent.id for agent in await list_meeting_participants(db, meeting.id)]
    close_meeting(meeting, summary, decisions, action_items, unresolved_questions)
    await return_participants_to_main_room(db, meeting, main_room)
    await extract_memories_from_meeting(db, meeting)
    await commit(db)
    bus.publish(MEETING_ENDED, serialize(meeting))
    return participant_ids


async def list_meeting_participants(db, meeting_id: uuid.UUID) -> list[Agent]:
    return await list_participants_ordered(db, meeting_id)


async def list_participants_ordered(db, meeting_id: uuid.UUID) -> list[Agent]:
    query = (
        select(Agent)
        .join(MeetingParticipant, MeetingParticipant.agent_id == Agent.id)
        .where(MeetingParticipant.meeting_id == meeting_id)
        .order_by(MeetingParticipant.round_robin_position)
    )
    return list((await db.execute(query)).scalars())


def close_meeting(meeting: Meeting, summary: str, decisions: list[str] | None, action_items: list[str] | None, unresolved_questions: list[str] | None) -> None:
    meeting.status = MeetingStatus.ENDED
    meeting.loop_state = MeetingLoopState.IDLE
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


async def open_meeting_turn(db, meeting_id: uuid.UUID, round_number: int, speaker_id: uuid.UUID) -> MeetingTurn:
    turn = MeetingTurn(id=uuid.uuid4(), meeting_id=meeting_id, round=round_number, speaker_id=speaker_id, state=MeetingTurnState.PROMPTED)
    db.add(turn)
    await commit(db)
    return turn


async def set_turn_run(db, turn: MeetingTurn, run_id: uuid.UUID) -> None:
    turn.run_id = run_id
    await commit(db)


async def mark_turn_streamed(db, turn: MeetingTurn) -> None:
    turn.state = MeetingTurnState.STREAMED
    await commit(db)


async def commit_turn(db, meeting: Meeting, turn: MeetingTurn, agent_id: uuid.UUID, content: str, next_round: int, next_speaker_id: uuid.UUID | None) -> MeetingMessage:
    """C5 step 5: the message, the turn's committed state, and the meeting's round/speaker pointer all land in one commit -- a crash between them must not resend or lose a turn that already produced output."""
    message = MeetingMessage(id=uuid.uuid4(), meeting_id=meeting.id, agent_id=agent_id, content=content, author=MeetingAuthor.AGENT)
    db.add(message)
    turn.state = MeetingTurnState.COMMITTED
    turn.message_id = message.id
    meeting.current_round = next_round
    meeting.next_speaker_id = next_speaker_id
    await commit(db)
    bus.publish(MEETING_MESSAGE, serialize(message))
    bus.publish(MEETING_UPDATED, serialize(meeting))
    return message


async def set_loop_state(db, meeting: Meeting, state: MeetingLoopState) -> None:
    meeting.loop_state = state
    await commit(db)
    bus.publish(MEETING_UPDATED, serialize(meeting))
