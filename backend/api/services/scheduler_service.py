import asyncio

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import commit
from models.agent import Agent, AgentStatus
from models.base import utcnow

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
