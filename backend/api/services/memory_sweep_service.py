import asyncio
import contextlib
import logging

from services.memory_consolidation_service import (
    archive_stale_memories,
    generate_consolidation_proposals,
)
from services.memory_embedding_service import sweep_missing_embeddings

logger = logging.getLogger(__name__)

SWEEP_INTERVAL_SECONDS = 300.0


def start_memory_sweep(session_factory) -> asyncio.Task:
    return asyncio.create_task(run_memory_sweep_loop(session_factory))


async def stop_memory_sweep(task: asyncio.Task) -> None:
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


def schedule_memory_sweep(session_factory) -> None:
    """A3.5: fired after a run finishes, but never awaited there -- landing, releasing the agent and promoting the queue is the critical path, not embedding or consolidation."""
    asyncio.create_task(run_memory_sweep_once_safely(session_factory))


async def run_memory_sweep_loop(session_factory) -> None:
    while True:
        await run_memory_sweep_once_safely(session_factory)
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)


async def run_memory_sweep_once_safely(session_factory) -> None:
    try:
        await run_memory_sweep_once(session_factory)
    except Exception:
        logger.exception("memory sweep failed")


async def run_memory_sweep_once(session_factory) -> None:
    async with session_factory() as db:
        await sweep_missing_embeddings(db)
        await generate_consolidation_proposals(db)
        await archive_stale_memories(db)
