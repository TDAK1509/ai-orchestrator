import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import get_db, get_runtime_service
from events.bus import bus
from events.schema import AGENT_CREATED, AGENT_FIRED
from lookups import get_active_or_404, get_or_404
from models.agent import Agent, AgentEffort
from models.team import Team
from serialization import serialize
from services.agent_service import (
    edit_agent,
    fire_agent,
    hire_agent,
    list_agents,
    restore_agent,
)

router = APIRouter(prefix="/agents", tags=["agents"])


class HireAgentBody(BaseModel):
    name: str
    role: str
    instructions: str = ""
    team_id: uuid.UUID | None = None
    model: str | None = None
    effort: AgentEffort | None = None


class EditAgentBody(BaseModel):
    name: str | None = None
    role: str | None = None
    instructions: str | None = None
    model: str | None = None
    effort: AgentEffort | None = None


@router.get("")
async def list_agents_route(db=Depends(get_db)):
    return [serialize(agent) for agent in await list_agents(db)]


@router.post("", status_code=201)
async def hire_agent_route(body: HireAgentBody, db=Depends(get_db)):
    if body.team_id is not None:
        await get_active_or_404(db, Team, body.team_id, "team")
    agent = await hire_agent(db, body.name, body.role, body.instructions, body.team_id, body.model, body.effort)
    bus.publish(AGENT_CREATED, serialize(agent))
    return serialize(agent)


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
