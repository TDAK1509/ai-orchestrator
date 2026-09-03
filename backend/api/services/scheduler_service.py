from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.agent import Agent, AgentStatus


async def has_free_slot(db: AsyncSession, max_concurrent_agents: int) -> bool:
    working = await count_working_agents(db)
    return working < max_concurrent_agents


async def count_working_agents(db: AsyncSession) -> int:
    query = select(func.count()).select_from(Agent).where(Agent.status == AgentStatus.WORKING)
    result = await db.execute(query)
    return result.scalar_one()


async def find_next_queued_agent(db: AsyncSession) -> Agent | None:
    query = select(Agent).where(Agent.status == AgentStatus.QUEUED).order_by(Agent.created_at).limit(1)
    result = await db.execute(query)
    return result.scalars().first()
