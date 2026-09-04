import asyncio
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import commit
from events.bus import bus
from events.schema import AGENT_STATUS_CHANGED
from models.agent import Agent, AgentStatus
from models.base import utcnow
from serialization import serialize

_SLOT_LOCK = asyncio.Lock()


async def claim_slot_or_queue(db: AsyncSession, agent: Agent, max_concurrent_agents: int) -> bool:
    """The free-slot check and the status flip that claims it happen under one lock, so two concurrent callers can't both see the same free slot."""
    async with _SLOT_LOCK:
        if await has_free_slot(db, max_concurrent_agents):
            agent.status = AgentStatus.WORKING
            agent.queued_at = None
        else:
            agent.status = AgentStatus.QUEUED
            agent.queued_at = utcnow()
        await commit(db)
        bus.publish(AGENT_STATUS_CHANGED, serialize(agent))
        return agent.status == AgentStatus.WORKING


async def claim_next_queued_agent(db: AsyncSession, max_concurrent_agents: int) -> Agent | None:
    async with _SLOT_LOCK:
        if not await has_free_slot(db, max_concurrent_agents):
            return None
        next_agent = await find_next_queued_agent(db)
        if next_agent is None:
            return None
        next_agent.status = AgentStatus.WORKING
        next_agent.queued_at = None
        await commit(db)
        bus.publish(AGENT_STATUS_CHANGED, serialize(next_agent))
        return next_agent


async def has_free_slot(db: AsyncSession, max_concurrent_agents: int) -> bool:
    working = await count_working_agents(db)
    return working < max_concurrent_agents


async def count_working_agents(db: AsyncSession) -> int:
    query = select(func.count()).select_from(Agent).where(Agent.status == AgentStatus.WORKING)
    result = await db.execute(query)
    return result.scalar_one()


async def find_next_queued_agent(db: AsyncSession) -> Agent | None:
    query = select(Agent).where(Agent.status == AgentStatus.QUEUED).order_by(Agent.queued_at).limit(1)
    result = await db.execute(query)
    return result.scalars().first()


async def claim_participants_or_fail(db: AsyncSession, agent_ids: list[uuid.UUID], max_concurrent_agents: int) -> bool:
    """C1: all participants or none -- a meeting that starts with only some of its roster claimed leaves the rest QUEUED with no task to promote them into (promote_next_queued_agent assumes a current_task_id)."""
    async with _SLOT_LOCK:
        agents = await load_agents(db, agent_ids)
        if not all(agent.status == AgentStatus.IDLE for agent in agents):
            return False
        if not await has_capacity_for(db, len(agents), max_concurrent_agents):
            return False
        claim_all_working(agents)
        await commit(db)
        publish_status_changes(agents)
        return True


async def load_agents(db: AsyncSession, agent_ids: list[uuid.UUID]) -> list[Agent]:
    query = select(Agent).where(Agent.id.in_(agent_ids))
    return list((await db.execute(query)).scalars())


async def has_capacity_for(db: AsyncSession, count: int, max_concurrent_agents: int) -> bool:
    working = await count_working_agents(db)
    return working + count <= max_concurrent_agents


def claim_all_working(agents: list[Agent]) -> None:
    for agent in agents:
        agent.status = AgentStatus.WORKING
        agent.queued_at = None


def publish_status_changes(agents: list[Agent]) -> None:
    for agent in agents:
        bus.publish(AGENT_STATUS_CHANGED, serialize(agent))


async def release_participants(db: AsyncSession, agent_ids: list[uuid.UUID]) -> None:
    async with _SLOT_LOCK:
        agents = await load_agents(db, agent_ids)
        for agent in agents:
            agent.status = AgentStatus.IDLE
        await commit(db)
        publish_status_changes(agents)
