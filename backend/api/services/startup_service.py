from sqlalchemy import select

from db import commit
from models.agent import Agent
from models.session import AgentSession, ExecutionRun
from runtime.runtime_service import RuntimeService
from services.decision_service import cancel_pending_decisions_for_agent
from services.room_service import ensure_main_room


async def reconcile_on_startup(db, runtime_service: RuntimeService) -> list[ExecutionRun]:
    """README 31.5: on startup, orphaned runs are marked failed, and (19.7) any decision they were blocked on can no longer be answered into a live process."""
    await backfill_roomless_agents_into_main_room(db)
    orphans = await runtime_service.reconcile_orphans()
    for run in orphans:
        await cancel_decisions_for_run(db, run)
    return orphans


async def backfill_roomless_agents_into_main_room(db) -> None:
    """Rule 1 (README 23): there is always a Main Room, and every active agent belongs to a room."""
    main_room = await ensure_main_room(db)
    query = select(Agent).where(Agent.room_id.is_(None), Agent.active.is_(True))
    roomless_agents = list((await db.execute(query)).scalars())
    for agent in roomless_agents:
        agent.room_id = main_room.id
    if roomless_agents:
        await commit(db)


async def cancel_decisions_for_run(db, run: ExecutionRun) -> None:
    agent_session = await db.get(AgentSession, run.agent_session_id)
    await cancel_pending_decisions_for_agent(db, agent_session.agent_id)
