import logging

from sqlalchemy import func, select

from models.agent import Agent, AgentStatus
from models.session import AgentSession, ExecutionRun, RunStatus
from models.task import Task, TaskStatus
from models.worktree import TaskWorktree
from runtime.runtime_service import RuntimeService
from services.resume_service import find_resume_pending_sessions
from services.run_driver import (
    drive_run_to_completion,
    finish_run,
    schedule_run_completion,
)

logger = logging.getLogger(__name__)


async def recover_running_runs(db, runtime_service: RuntimeService, repo_root, policy) -> None:
    """Track B1: the one explicit, idempotent pass over every run this backend does not know the outcome of. A bad session must not abort startup for the rest (B2.8)."""
    for run in await find_running_runs(db):
        await recover_one_run_safely(db, runtime_service, repo_root, run, policy)
    await sweep_dangling_agents(db, runtime_service, repo_root, policy)
    await resume_pending_sessions(db, runtime_service, repo_root, policy)
    await recover_meeting_runs(db, runtime_service)


async def find_running_runs(db) -> list[ExecutionRun]:
    """C4: a meeting-bound session branches to recover_meeting_runs instead -- it has no task to reattach, resume or drive through finish_task_run."""
    query = (
        select(ExecutionRun)
        .join(AgentSession, ExecutionRun.agent_session_id == AgentSession.id)
        .where(ExecutionRun.status == RunStatus.RUNNING, AgentSession.meeting_id.is_(None))
    )
    return list((await db.execute(query)).scalars())


async def recover_meeting_runs(db, runtime_service: RuntimeService) -> None:
    """C4/C5: a meeting's long-lived process is never adoptable across a restart -- terminate it on sight and pause its loop; a human (or the next scheduled round) resumes the conversation later via --resume."""
    for run in await find_running_meeting_runs(db):
        await recover_one_meeting_run_safely(db, runtime_service, run)


async def find_running_meeting_runs(db) -> list[ExecutionRun]:
    query = (
        select(ExecutionRun)
        .join(AgentSession, ExecutionRun.agent_session_id == AgentSession.id)
        .where(ExecutionRun.status == RunStatus.RUNNING, AgentSession.meeting_id.isnot(None))
    )
    return list((await db.execute(query)).scalars())


async def recover_one_meeting_run_safely(db, runtime_service: RuntimeService, run: ExecutionRun) -> None:
    try:
        await recover_one_meeting_run(db, runtime_service, run)
    except Exception:
        logger.exception("failed to recover meeting run %s at startup", run.id)


async def recover_one_meeting_run(db, runtime_service: RuntimeService, run: ExecutionRun) -> None:
    agent_session = await db.get(AgentSession, run.agent_session_id)
    await runtime_service.finalize_meeting_run(run.id)
    await pause_meeting_for_session(db, agent_session)


async def pause_meeting_for_session(db, agent_session: AgentSession) -> None:
    from models.meeting import Meeting, MeetingLoopState, MeetingStatus
    from services.meeting_service import set_loop_state

    meeting = await db.get(Meeting, agent_session.meeting_id)
    if meeting is not None and meeting.status == MeetingStatus.ACTIVE:
        await set_loop_state(db, meeting, MeetingLoopState.PAUSED)


async def recover_one_run_safely(db, runtime_service, repo_root, run: ExecutionRun, policy) -> None:
    try:
        await recover_one_run(db, runtime_service, repo_root, run, policy)
    except Exception:
        logger.exception("failed to recover execution run %s at startup", run.id)


async def recover_one_run(db, runtime_service, repo_root, run: ExecutionRun, policy) -> None:
    agent_session = await db.get(AgentSession, run.agent_session_id)
    managed = runtime_service.resolve_process(agent_session.agent_id, run)
    if managed.is_alive():
        await reattach_live_run(db, runtime_service, repo_root, agent_session, run, policy)
    else:
        await drive_run_to_completion(runtime_service, repo_root, agent_session.agent_id, *await task_context(db, agent_session), run.id, policy)


async def task_context(db, agent_session: AgentSession) -> tuple:
    agent = await db.get(Agent, agent_session.agent_id)
    return agent.current_task_id, agent_session.task_worktree_id


async def reattach_live_run(db, runtime_service, repo_root, agent_session: AgentSession, run: ExecutionRun, policy) -> None:
    """A process that survived the crash keeps running either way; this just puts a driver back on it instead of leaving it unsupervised (Phase 0's whole point)."""
    task_id, task_worktree_id = await task_context(db, agent_session)
    if task_id is None:
        return
    schedule_run_completion(runtime_service, repo_root, agent_session.agent_id, task_id, task_worktree_id, run.id, policy)


async def sweep_dangling_agents(db, runtime_service, repo_root, policy) -> None:
    """B1: an agent/task pair whose last run already finished, but whose backend died before finish_task_run recorded the outcome, is stuck with no RUNNING row for the loop above to find at all. Excludes any agent the loop above already reattached or drained -- that agent's current run may still be genuinely in flight, and its *older* terminal runs must never be re-finished (codex P0: this used to pick the wrong run and could land the wrong worktree)."""
    for agent in await find_dangling_working_agents(db):
        await sweep_one_agent_safely(db, runtime_service, repo_root, agent, policy)


async def find_dangling_working_agents(db) -> list[Agent]:
    query = select(Agent).where(Agent.status.in_((AgentStatus.WORKING, AgentStatus.BLOCKED)), Agent.current_task_id.isnot(None))
    candidates = list((await db.execute(query)).scalars())
    return [agent for agent in candidates if not await has_running_run(db, agent.id)]


async def has_running_run(db, agent_id) -> bool:
    query = (
        select(func.count())
        .select_from(ExecutionRun)
        .join(AgentSession, ExecutionRun.agent_session_id == AgentSession.id)
        .where(AgentSession.agent_id == agent_id, ExecutionRun.status == RunStatus.RUNNING)
    )
    return (await db.execute(query)).scalar_one() > 0


async def sweep_one_agent_safely(db, runtime_service, repo_root, agent: Agent, policy) -> None:
    try:
        await sweep_one_agent(db, runtime_service, repo_root, agent, policy)
    except Exception:
        logger.exception("failed to sweep dangling agent %s at startup", agent.id)


async def sweep_one_agent(db, runtime_service, repo_root, agent: Agent, policy) -> None:
    task = await db.get(Task, agent.current_task_id)
    if task is None or task.status != TaskStatus.IN_PROGRESS:
        return
    run = await find_latest_terminal_run_for_task(db, agent.id, task.id)
    if run is None:
        return
    task_worktree = await db.get(TaskWorktree, (await db.get(AgentSession, run.agent_session_id)).task_worktree_id)
    await finish_run(db, runtime_service, repo_root, agent, task, task_worktree, run, policy)


async def find_latest_terminal_run_for_task(db, agent_id, task_id) -> ExecutionRun | None:
    """Scoped to the agent's *current* task, not just its most recent run of any kind -- an agent's last-completed run could otherwise belong to an unrelated, already-landed task."""
    query = (
        select(ExecutionRun)
        .join(AgentSession, ExecutionRun.agent_session_id == AgentSession.id)
        .join(TaskWorktree, AgentSession.task_worktree_id == TaskWorktree.id)
        .where(AgentSession.agent_id == agent_id, TaskWorktree.task_id == task_id, ExecutionRun.status != RunStatus.RUNNING)
        .order_by(ExecutionRun.completed_at.desc())
        .limit(1)
    )
    return (await db.execute(query)).scalars().first()


async def resume_pending_sessions(db, runtime_service, repo_root, policy) -> None:
    """B2.4: promote every durable resume intent at startup, not just the one this pass's own drive_run_to_completion happened to create."""
    for agent_session in await find_resume_pending_sessions(db):
        await resume_one_session_safely(db, runtime_service, repo_root, agent_session, policy)


async def resume_one_session_safely(db, runtime_service, repo_root, agent_session: AgentSession, policy) -> None:
    try:
        await resume_one_session(db, runtime_service, repo_root, agent_session, policy)
    except Exception:
        logger.exception("failed to resume agent session %s at startup", agent_session.id)


async def resume_one_session(db, runtime_service, repo_root, agent_session: AgentSession, policy) -> None:
    # allow-comment: deferred import breaks the cycle -- task_service imports schedule_run_completion (via run_driver) at load time, so this module cannot import task_service at load time too.
    from services.task_service import fail_task, try_resume_agent_session

    agent = await db.get(Agent, agent_session.agent_id)
    task = await db.get(Task, agent.current_task_id) if agent.current_task_id else None
    if task is None:
        return
    task_worktree = await db.get(TaskWorktree, agent_session.task_worktree_id)
    run = await find_latest_terminal_run_for_task(db, agent.id, task.id)
    if not await try_resume_agent_session(db, runtime_service, repo_root, agent, task, task_worktree, agent_session, policy) and run is not None:
        await fail_task(db, agent, task, run)
