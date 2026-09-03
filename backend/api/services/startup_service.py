from models.session import AgentSession, ExecutionRun
from runtime.runtime_service import RuntimeService
from services.decision_service import cancel_pending_decisions_for_agent


async def reconcile_on_startup(db, runtime_service: RuntimeService) -> list[ExecutionRun]:
    """README 31.5: on startup, orphaned runs are marked failed, and (19.7) any decision they were blocked on can no longer be answered into a live process."""
    orphans = await runtime_service.reconcile_orphans()
    for run in orphans:
        await cancel_decisions_for_run(db, run)
    return orphans


async def cancel_decisions_for_run(db, run: ExecutionRun) -> None:
    agent_session = await db.get(AgentSession, run.agent_session_id)
    await cancel_pending_decisions_for_agent(db, agent_session.agent_id)
