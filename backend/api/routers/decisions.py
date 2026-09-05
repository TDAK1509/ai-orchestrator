import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import get_db
from lookups import get_or_404
from models.agent import Agent
from models.session import AgentSession
from models.task import Task
from models.worktree import TaskWorktree
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
    agent_session = await get_or_404(db, AgentSession, body.agent_session_id, "agent_session")
    require_session_belongs_to_agent(agent_session, agent)
    task = await resolve_decision_task(db, agent_session, body.task_id)
    decision = await create_decision_request(
        db, agent, task, body.question, body.options, body.allow_custom_answer, body.agent_session_id
    )
    return serialize(decision)


def require_session_belongs_to_agent(agent_session: AgentSession, agent: Agent) -> None:
    """A mismatched pair must 404, not silently block whichever agent the caller happened to name (codex: an unrelated agent/task could otherwise be blocked by a forged or buggy request)."""
    if agent_session.agent_id != agent.id:
        raise HTTPException(status_code=404, detail="agent_session not found")


async def resolve_decision_task(db, agent_session: AgentSession, task_id: uuid.UUID | None) -> Task | None:
    if task_id is None:
        return None
    task = await get_or_404(db, Task, task_id, "task")
    task_worktree = await db.get(TaskWorktree, agent_session.task_worktree_id) if agent_session.task_worktree_id else None
    if task_worktree is None or task_worktree.task_id != task.id:
        raise HTTPException(status_code=404, detail="task does not belong to this agent_session")
    return task


@router.post("/{decision_id}/answer")
async def answer_decision_route(decision_id: uuid.UUID, body: AnswerDecisionBody, db=Depends(get_db)):
    decision = await answer_decision(db, decision_id, body.answer)
    return serialize(decision)
