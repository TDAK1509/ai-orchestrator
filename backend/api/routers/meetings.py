import uuid
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from deps import get_db, get_policy, get_repo_root, get_runtime_service
from lookups import get_or_404
from models.agent import Agent
from models.meeting import Meeting, MeetingLoopState
from runtime.meeting_runtime import (
    force_close_out,
    run_single_round,
    start_meeting_loop,
)
from runtime.runtime_service import RuntimeService
from serialization import serialize
from services.meeting_service import (
    add_human_message,
    create_meeting,
    end_meeting,
    list_meeting_messages,
    list_meetings,
    set_loop_state,
)
from services.room_service import ensure_main_room
from services.task_service import TaskRuntimePolicy

router = APIRouter(prefix="/meetings", tags=["meetings"])


class CreateMeetingBody(BaseModel):
    topic: str
    goal: str | None = None
    participant_agent_ids: list[uuid.UUID]
    facilitator_instructions: str | None = None
    max_rounds: int = 3
    chair_agent_id: uuid.UUID | None = None


class AddMeetingMessageBody(BaseModel):
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
async def create_meeting_route(body: CreateMeetingBody, db=Depends(get_db), policy: TaskRuntimePolicy = Depends(get_policy)):
    participants = await load_participants(db, body.participant_agent_ids)
    meeting = await create_meeting(db, body.topic, body.goal, participants, policy, body.facilitator_instructions, body.max_rounds, body.chair_agent_id)
    return serialize(meeting)


async def load_participants(db, agent_ids: list[uuid.UUID]) -> list[Agent]:
    query = select(Agent).where(Agent.id.in_(agent_ids))
    return list((await db.execute(query)).scalars())


@router.get("/{meeting_id}/messages")
async def list_meeting_messages_route(meeting_id: uuid.UUID, db=Depends(get_db)):
    return [serialize(message) for message in await list_meeting_messages(db, meeting_id)]


@router.post("/{meeting_id}/messages", status_code=201)
async def add_meeting_message_route(meeting_id: uuid.UUID, body: AddMeetingMessageBody, db=Depends(get_db)):
    """C7: a human interjection, not a simulated agent turn -- an agent's own turn comes only from the meeting runtime now."""
    meeting = await get_or_404(db, Meeting, meeting_id, "meeting")
    message = await add_human_message(db, meeting, body.content)
    return serialize(message)


@router.post("/{meeting_id}/start")
async def start_meeting_route(meeting_id: uuid.UUID, db=Depends(get_db), runtime_service: RuntimeService = Depends(get_runtime_service), repo_root: Path = Depends(get_repo_root), policy: TaskRuntimePolicy = Depends(get_policy)):
    meeting = await get_or_404(db, Meeting, meeting_id, "meeting")
    start_meeting_loop(runtime_service, repo_root, policy, meeting.id)
    return serialize(meeting)


@router.post("/{meeting_id}/run-round")
async def run_round_route(meeting_id: uuid.UUID, db=Depends(get_db), runtime_service: RuntimeService = Depends(get_runtime_service), repo_root: Path = Depends(get_repo_root), policy: TaskRuntimePolicy = Depends(get_policy)):
    meeting = await get_or_404(db, Meeting, meeting_id, "meeting")
    await run_single_round(runtime_service, repo_root, policy, meeting.id)
    return serialize(await db.get(Meeting, meeting_id))


@router.post("/{meeting_id}/pause")
async def pause_meeting_route(meeting_id: uuid.UUID, db=Depends(get_db)):
    meeting = await get_or_404(db, Meeting, meeting_id, "meeting")
    await set_loop_state(db, meeting, MeetingLoopState.PAUSED)
    return serialize(meeting)


@router.post("/{meeting_id}/stop")
async def stop_meeting_route(meeting_id: uuid.UUID, db=Depends(get_db)):
    """C5 guard: Stop cancels the loop and sets loop_state = paused -- the same effect as pause, kept as a separate route for a distinct button in the panel."""
    meeting = await get_or_404(db, Meeting, meeting_id, "meeting")
    await set_loop_state(db, meeting, MeetingLoopState.PAUSED)
    return serialize(meeting)


@router.post("/{meeting_id}/summarize")
async def summarize_meeting_route(meeting_id: uuid.UUID, db=Depends(get_db), runtime_service: RuntimeService = Depends(get_runtime_service), repo_root: Path = Depends(get_repo_root), policy: TaskRuntimePolicy = Depends(get_policy)):
    meeting = await get_or_404(db, Meeting, meeting_id, "meeting")
    await force_close_out(runtime_service, repo_root, policy, meeting.id)
    return serialize(await db.get(Meeting, meeting_id))


@router.post("/{meeting_id}/end")
async def end_meeting_route(meeting_id: uuid.UUID, body: EndMeetingBody, db=Depends(get_db), runtime_service: RuntimeService = Depends(get_runtime_service), repo_root: Path = Depends(get_repo_root), policy: TaskRuntimePolicy = Depends(get_policy)):
    meeting = await get_or_404(db, Meeting, meeting_id, "meeting")
    main_room = await ensure_main_room(db)
    meeting = await end_meeting(db, runtime_service, repo_root, policy, meeting, main_room, body.summary, body.decisions, body.action_items, body.unresolved_questions)
    return serialize(meeting)
