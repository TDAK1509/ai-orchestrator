from pathlib import Path

from sqlalchemy import select

from db import commit
from models.agent import Agent
from runtime.runtime_service import RuntimeService
from services.recovery_service import recover_running_runs
from services.room_service import ensure_main_room
from services.task_service import TaskRuntimePolicy


async def reconcile_on_startup(db, runtime_service: RuntimeService, repo_root: Path, policy: TaskRuntimePolicy) -> None:
    """README 31.5, Track B1/B2: every run this backend doesn't already know the outcome of is reattached, drained, resumed or (only once resume is exhausted) blocked."""
    await backfill_roomless_agents_into_main_room(db)
    await recover_running_runs(db, runtime_service, repo_root, policy)


async def backfill_roomless_agents_into_main_room(db) -> None:
    """Rule 1 (README 23): there is always a Main Room, and every active agent belongs to a room."""
    main_room = await ensure_main_room(db)
    query = select(Agent).where(Agent.room_id.is_(None), Agent.active.is_(True))
    roomless_agents = list((await db.execute(query)).scalars())
    for agent in roomless_agents:
        agent.room_id = main_room.id
    if roomless_agents:
        await commit(db)
