import asyncio
import contextlib
import logging
import uuid
from datetime import UTC

from sqlalchemy import select

from db import commit
from events.bus import bus
from events.schema import ATTENTION_CREATED
from models.attention import AttentionEvent, AttentionType
from models.base import utcnow
from models.session import AgentSession, ExecutionRun, RunStatus
from runtime.runtime_service import RuntimeService
from serialization import serialize
from services.decision_service import has_pending_decision

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 30.0
STALL_WARNING_SECONDS = 300.0
STALL_KILL_SECONDS = 1800.0

_warned_runs: set[uuid.UUID] = set()


def start_watchdog(runtime_service: RuntimeService) -> asyncio.Task:
    return asyncio.create_task(run_watchdog_loop(runtime_service))


async def stop_watchdog(task: asyncio.Task) -> None:
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def run_watchdog_loop(runtime_service: RuntimeService) -> None:
    while True:
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        await sweep_running_runs_safely(runtime_service)


async def sweep_running_runs_safely(runtime_service: RuntimeService) -> None:
    try:
        await sweep_running_runs(runtime_service)
    except Exception:
        logger.exception("watchdog sweep failed")


async def sweep_running_runs(runtime_service: RuntimeService) -> None:
    async with runtime_service.session_factory() as db:
        for run in await find_running_runs(db):
            await check_one_run(db, runtime_service, run)


async def find_running_runs(db) -> list[ExecutionRun]:
    query = select(ExecutionRun).where(ExecutionRun.status == RunStatus.RUNNING)
    return list((await db.execute(query)).scalars())


async def check_one_run(db, runtime_service: RuntimeService, run: ExecutionRun) -> None:
    """B3: silence alone proves nothing -- ask_human's wait_for_answer legitimately produces none while it waits on a human, so a pending decision always wins over the clock."""
    silence = silence_seconds(run)
    if silence < STALL_WARNING_SECONDS:
        _warned_runs.discard(run.id)
        return
    agent_session = await db.get(AgentSession, run.agent_session_id)
    if await has_pending_decision(db, agent_session.agent_id):
        return
    await warn_or_kill(db, runtime_service, run, silence)


async def warn_or_kill(db, runtime_service: RuntimeService, run: ExecutionRun, silence: float) -> None:
    if silence >= STALL_KILL_SECONDS:
        _warned_runs.discard(run.id)
        await runtime_service.kill_run(run.id)
    elif run.id not in _warned_runs:
        _warned_runs.add(run.id)
        await raise_stall_warning(db, run)


def silence_seconds(run: ExecutionRun) -> float:
    reference = run.last_event_at or run.started_at
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=UTC)
    return (utcnow() - reference).total_seconds()


async def raise_stall_warning(db, run: ExecutionRun) -> None:
    agent_session = await db.get(AgentSession, run.agent_session_id)
    event = build_stall_attention_event(agent_session)
    db.add(event)
    await commit(db)
    bus.publish(ATTENTION_CREATED, serialize(event))


def build_stall_attention_event(agent_session: AgentSession) -> AttentionEvent:
    return AttentionEvent(
        id=uuid.uuid4(),
        type=AttentionType.AGENT_BLOCKED,
        agent_id=agent_session.agent_id,
        title="Run possibly stalled",
        message=f"Agent session {agent_session.id} has produced no output for over {int(STALL_WARNING_SECONDS)}s.",
    )
