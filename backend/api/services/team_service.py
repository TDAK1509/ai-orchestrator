import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import commit
from models.agent import Agent
from models.memory import MemoryStatus
from models.team import Team
from services.memory_service import list_team_memories


async def create_team(db: AsyncSession, name: str, description: str = "") -> Team:
    team = Team(id=uuid.uuid4(), name=name, description=description)
    db.add(team)
    await commit(db)
    return team


async def list_teams(db: AsyncSession) -> list[Team]:
    query = select(Team).where(Team.active.is_(True)).order_by(Team.created_at)
    return list((await db.execute(query)).scalars())


async def list_team_agents(db: AsyncSession, team_id: uuid.UUID) -> list[Agent]:
    query = select(Agent).where(Agent.team_id == team_id, Agent.active.is_(True))
    return list((await db.execute(query)).scalars())


async def assign_agent_to_team(db: AsyncSession, agent: Agent, team: Team) -> Agent:
    agent.team_id = team.id
    await commit(db)
    return agent


async def unassign_agent(db: AsyncSession, agent: Agent) -> Agent:
    agent.team_id = None
    await commit(db)
    return agent


async def archive_team(db: AsyncSession, team: Team) -> Team:
    """Never a hard delete, mirroring fire_agent: archive the team's memory and clear team_id off every referencing agent first, so nothing is left pointing at an archived team, then flip the team itself. One commit for all of it (README 32.4's reasoning applies here too): archive_memory's own per-record commit is bypassed on purpose, so a crash partway never leaves the team inactive with only some memories archived."""
    team.active = False
    await archive_team_memories(db, team.id)
    await clear_team_from_agents(db, team.id)
    await commit(db)
    return team


async def archive_team_memories(db: AsyncSession, team_id: uuid.UUID) -> None:
    for record in await list_team_memories(db, team_id):
        record.status = MemoryStatus.ARCHIVED


async def clear_team_from_agents(db: AsyncSession, team_id: uuid.UUID) -> None:
    """Every agent, not just active ones (list_team_agents excludes fired agents): fire_agent leaves a fired row's team_id in place, and that row would still block the team's FK otherwise."""
    query = select(Agent).where(Agent.team_id == team_id)
    for agent in (await db.execute(query)).scalars():
        agent.team_id = None
