import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import get_db
from lookups import get_or_404
from models.agent import Agent
from models.team import Team
from serialization import serialize
from services.team_service import (
    archive_team,
    assign_agent_to_team,
    create_team,
    list_team_agents,
    list_teams,
    unassign_agent,
)

router = APIRouter(prefix="/teams", tags=["teams"])


class CreateTeamBody(BaseModel):
    name: str
    description: str = ""


@router.get("")
async def list_teams_route(db=Depends(get_db)):
    return [serialize(team) for team in await list_teams(db)]


@router.post("", status_code=201)
async def create_team_route(body: CreateTeamBody, db=Depends(get_db)):
    team = await create_team(db, body.name, body.description)
    return serialize(team)


@router.get("/{team_id}/agents")
async def list_team_agents_route(team_id: uuid.UUID, db=Depends(get_db)):
    await get_or_404(db, Team, team_id, "team")
    return [serialize(agent) for agent in await list_team_agents(db, team_id)]


@router.post("/{team_id}/agents/{agent_id}")
async def assign_agent_to_team_route(team_id: uuid.UUID, agent_id: uuid.UUID, db=Depends(get_db)):
    team = await get_or_404(db, Team, team_id, "team")
    agent = await get_or_404(db, Agent, agent_id, "agent")
    agent = await assign_agent_to_team(db, agent, team)
    return serialize(agent)


@router.delete("/{team_id}/agents/{agent_id}")
async def unassign_agent_route(team_id: uuid.UUID, agent_id: uuid.UUID, db=Depends(get_db)):
    await get_or_404(db, Team, team_id, "team")
    agent = await get_or_404(db, Agent, agent_id, "agent")
    agent = await unassign_agent(db, agent)
    return serialize(agent)


@router.delete("/{team_id}")
async def archive_team_route(team_id: uuid.UUID, db=Depends(get_db)):
    team = await get_or_404(db, Team, team_id, "team")
    team = await archive_team(db, team)
    return serialize(team)
