from pathlib import Path

from sqlalchemy import select

from db import commit
from models.base import utcnow
from models.checkpoint import AgentCheckpoint
from models.session import AgentSession, ExecutionRun, RunStatus
from runtime.mcp_config import McpServerRef
from runtime.process import terminate_pid
from runtime.runtime_service import RuntimeService
from services.checkpoint_service import extract_memories_from_checkpoint
from services.context_builder import build_initial_message
from services.run_driver import schedule_run_completion


async def rotate_session(db, runtime_service: RuntimeService, repo_root: Path, agent, task, task_worktree, old_agent_session: AgentSession, checkpoint: AgentCheckpoint, allowed_servers: list[McpServerRef], policy) -> ExecutionRun:
    """README 17.5: the agent and the worktree survive; only the conversation is replaced. Spawns and schedules the replacement before touching anything irreversible, so a failure here leaves the old session live and the checkpoint still usable for a retry, instead of an agent with neither an old nor a new session."""
    await stop_if_running(db, old_agent_session)
    message = await build_initial_message(db, agent, task, repo_root, allowed_servers, checkpoint)
    run = await runtime_service.spawn(agent, task_worktree, allowed_servers, message)
    schedule_run_completion(runtime_service, repo_root, agent.id, task.id, task_worktree.id, run.id, policy)
    await archive_session(db, old_agent_session)
    await extract_memories_from_checkpoint(db, checkpoint)
    return run


async def stop_if_running(db, old_agent_session: AgentSession) -> None:
    run = await find_running_run_for_session(db, old_agent_session.id)
    if run is not None and run.pid is not None:
        await terminate_pid(run.pid)


async def find_running_run_for_session(db, agent_session_id) -> ExecutionRun | None:
    query = select(ExecutionRun).where(ExecutionRun.agent_session_id == agent_session_id, ExecutionRun.status == RunStatus.RUNNING)
    return (await db.execute(query)).scalars().first()


async def archive_session(db, agent_session: AgentSession) -> None:
    agent_session.ended_at = utcnow()
    await commit(db)
