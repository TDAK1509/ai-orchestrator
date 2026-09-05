import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import get_db
from lookups import get_or_404
from models.agent import Agent
from models.task import Task
from serialization import serialize
from services.decision_service import (
    answer_decision,
    create_decision_request,
    list_pending_decisions,
)

router = APIRouter(prefix="/decisions", tags=["decisions"])


class AnswerDecisionBody(BaseModel):
    answer: str


class CreateDecisionBody(BaseModel):
    agent_id: uuid.UUID
    agent_session_id: uuid.UUID
    task_id: uuid.UUID | None = None
    question: str
    options: list[dict] | None = None
    allow_custom_answer: bool = True


@router.get("")
async def list_pending_decisions_route(db=Depends(get_db)):
    return [serialize(decision) for decision in await list_pending_decisions(db)]


@router.post("")
async def create_decision_route(body: CreateDecisionBody, db=Depends(get_db)):
    """PR 1: called from the ask_human MCP subprocess over HTTP, not in-process, so the publish this triggers reaches the WebSocket subscribers living in this backend process."""
    agent = await get_or_404(db, Agent, body.agent_id, "agent")
    task = await db.get(Task, body.task_id) if body.task_id is not None else None
    decision = await create_decision_request(
        db, agent, task, body.question, body.options, body.allow_custom_answer, body.agent_session_id
    )
    return serialize(decision)


@router.post("/{decision_id}/answer")
async def answer_decision_route(decision_id: uuid.UUID, body: AnswerDecisionBody, db=Depends(get_db)):
    decision = await answer_decision(db, decision_id, body.answer)
    return serialize(decision)
