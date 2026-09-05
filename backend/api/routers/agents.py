import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from deps import get_db, get_policy, get_repo_root, get_runtime_service
from events.bus import bus
from events.schema import AGENT_CREATED, AGENT_FIRED
from lookups import get_active_or_404, get_or_404
from models.agent import Agent, AgentEffort
from models.skill import Skill
from models.team import Team
from serialization import serialize
from services.agent_service import (
    edit_agent,
    fire_agent,
    hire_agent,
    list_agents,
    restore_agent,
    stop_agent,
)
from services.task_service import send_message_to_agent

router = APIRouter(prefix="/agents", tags=["agents"])

# allow-comment: the catalog holds 12 skills today -- this cap keeps one hire request from issuing an unbounded number of skill lookups, not from ever matching the catalog's real size.
MAX_HIRE_SKILL_IDS = 50


class HireAgentBody(BaseModel):
    name: str
    role: str
    instructions: str = ""
    team_id: uuid.UUID | None = None
    model: str | None = None
    effort: AgentEffort | None = None
    skill_ids: list[uuid.UUID] = Field(default_factory=list, max_length=MAX_HIRE_SKILL_IDS)


class EditAgentBody(BaseModel):
    name: str | None = None
    role: str | None = None
    instructions: str | None = None
    model: str | None = None
    effort: AgentEffort | None = None


class SendMessageBody(BaseModel):
    # allow-comment: bounds a human-authored prompt the way MAX_HIRE_SKILL_IDS bounds skill_ids above -- large enough for a real message, small enough to cap the prompt/process one bad request can trigger.
    content: str = Field(min_length=1, max_length=20000)


@router.get("")
async def list_agents_route(db=Depends(get_db)):
    return [serialize(agent) for agent in await list_agents(db)]


@router.post("", status_code=201)
async def hire_agent_route(body: HireAgentBody, db=Depends(get_db)):
    if body.team_id is not None:
        await get_active_or_404(db, Team, body.team_id, "team")
    skills = await load_skills(db, body.skill_ids)
    agent = await hire_agent(db, body.name, body.role, body.instructions, body.team_id, body.model, body.effort, skills)
    bus.publish(AGENT_CREATED, serialize(agent))
    return serialize(agent)


async def load_skills(db, skill_ids: list[uuid.UUID]) -> list[Skill]:
    """One query for the whole list, not one per id -- a hire can name up to MAX_HIRE_SKILL_IDS of them."""
    unique_ids = list(dict.fromkeys(skill_ids))
    found = {skill.id: skill for skill in (await db.execute(select(Skill).where(Skill.id.in_(unique_ids)))).scalars()}
    require_all_found(unique_ids, found)
    return [found[skill_id] for skill_id in unique_ids]


def require_all_found(skill_ids: list[uuid.UUID], found: dict[uuid.UUID, Skill]) -> None:
    missing = [skill_id for skill_id in skill_ids if skill_id not in found]
    if missing:
        raise HTTPException(status_code=404, detail=f"skill not found: {missing[0]}")


@router.get("/{agent_id}")
async def get_agent_route(agent_id: uuid.UUID, db=Depends(get_db)):
    agent = await get_or_404(db, Agent, agent_id, "agent")
    return serialize(agent)


@router.patch("/{agent_id}")
async def edit_agent_route(agent_id: uuid.UUID, body: EditAgentBody, db=Depends(get_db)):
    agent = await get_or_404(db, Agent, agent_id, "agent")
    agent = await edit_agent(db, agent, body, body.model_fields_set)
    return serialize(agent)


@router.delete("/{agent_id}")
async def fire_agent_route(agent_id: uuid.UUID, db=Depends(get_db), runtime_service=Depends(get_runtime_service)):
    agent = await get_or_404(db, Agent, agent_id, "agent")
    agent = await fire_agent(db, runtime_service, agent)
    bus.publish(AGENT_FIRED, serialize(agent))
    return serialize(agent)


@router.post("/{agent_id}/restore")
async def restore_agent_route(agent_id: uuid.UUID, db=Depends(get_db)):
    agent = await get_or_404(db, Agent, agent_id, "agent")
    agent = await restore_agent(db, agent)
    return serialize(agent)


@router.post("/{agent_id}/stop")
async def stop_agent_route(agent_id: uuid.UUID, db=Depends(get_db), runtime_service=Depends(get_runtime_service)):
    """B2: Esc in the sheet -- interrupts the current run by killing it (README 19's "Stop", not a soft turn-interrupt)."""
    agent = await get_or_404(db, Agent, agent_id, "agent")
    run = await stop_agent(db, runtime_service, agent)
    return {"stopped": run is not None}


@router.post("/{agent_id}/message")
async def send_agent_message_route(
    agent_id: uuid.UUID, body: SendMessageBody, db=Depends(get_db),
    runtime_service=Depends(get_runtime_service), repo_root=Depends(get_repo_root), policy=Depends(get_policy),
):
    """PR 1: resumes the agent's own last session with a human's text -- one message is one run, the reply arrives on the existing activity feed."""
    agent = await get_or_404(db, Agent, agent_id, "agent")
    run = await send_message_to_agent(db, runtime_service, repo_root, agent, body.content, policy)
    return serialize(run)
