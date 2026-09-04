import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from deps import get_db
from events.bus import bus
from events.schema import MEETING_CREATED, MEETING_ENDED, MEETING_MESSAGE
from lookups import get_or_404
from models.agent import Agent
from models.meeting import Meeting
from serialization import serialize
from services.meeting_service import (
    add_meeting_message,
    create_meeting,
    end_meeting,
    list_meeting_messages,
    list_meetings,
)
from services.room_service import ensure_main_room

router = APIRouter(prefix="/meetings", tags=["meetings"])


class CreateMeetingBody(BaseModel):
    topic: str
    goal: str | None = None
    participant_agent_ids: list[uuid.UUID]


class AddMeetingMessageBody(BaseModel):
    agent_id: uuid.UUID
    content: str


class EndMeetingBody(BaseModel):
    summary: str
    decisions: list[str] | None = None
    action_items: list[str] | None = None
    unresolved_questions: list[str] | None = None


@router.get("")
async def list_meetings_route(db=Depends(get_db)):
    return [serialize(meeting) for meeting in await list_meetings(db)]


@router.post("", status_code=201)
async def create_meeting_route(body: CreateMeetingBody, db=Depends(get_db)):
    participants = await load_participants(db, body.participant_agent_ids)
    meeting = await create_meeting(db, body.topic, body.goal, participants)
    bus.publish(MEETING_CREATED, serialize(meeting))
    return serialize(meeting)


async def load_participants(db, agent_ids: list[uuid.UUID]) -> list[Agent]:
    query = select(Agent).where(Agent.id.in_(agent_ids))
    return list((await db.execute(query)).scalars())


@router.get("/{meeting_id}/messages")
async def list_meeting_messages_route(meeting_id: uuid.UUID, db=Depends(get_db)):
    return [serialize(message) for message in await list_meeting_messages(db, meeting_id)]


@router.post("/{meeting_id}/messages", status_code=201)
async def add_meeting_message_route(meeting_id: uuid.UUID, body: AddMeetingMessageBody, db=Depends(get_db)):
    meeting, agent = await load_meeting_and_agent(db, meeting_id, body.agent_id)
    message = await add_meeting_message(db, meeting, agent, body.content)
    bus.publish(MEETING_MESSAGE, serialize(message))
    return serialize(message)


async def load_meeting_and_agent(db, meeting_id: uuid.UUID, agent_id: uuid.UUID):
    meeting = await get_or_404(db, Meeting, meeting_id, "meeting")
    agent = await get_or_404(db, Agent, agent_id, "agent")
    return meeting, agent


@router.post("/{meeting_id}/end")
async def end_meeting_route(meeting_id: uuid.UUID, body: EndMeetingBody, db=Depends(get_db)):
    meeting = await get_or_404(db, Meeting, meeting_id, "meeting")
    main_room = await ensure_main_room(db)
    meeting = await end_meeting(db, meeting, main_room, body.summary, body.decisions, body.action_items, body.unresolved_questions)
    bus.publish(MEETING_ENDED, serialize(meeting))
    return serialize(meeting)
