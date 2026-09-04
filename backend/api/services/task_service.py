import asyncio
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from db import commit
from events.bus import bus
from events.schema import (
    AGENT_STATUS_CHANGED,
    ATTENTION_CREATED,
    TASK_BLOCKED,
    TASK_COMPLETED,
)
from models.agent import Agent, AgentStatus
from models.attention import AttentionEvent, AttentionType
from models.base import utcnow
from models.merge import MergeType, PrStatus, TaskMerge
from models.session import AgentSession, ExecutionRun, RunStatus
from models.task import Task, TaskPriority, TaskStatus
from models.worktree import TaskWorktree
from runtime import landing
from runtime import worktree as worktree_ops
from runtime.mcp_config import McpServerRef
from runtime.runtime_service import RuntimeService
from serialization import serialize
from services.checkpoint_service import (
    extract_memories_on_task_completion,
    find_latest_unused_checkpoint,
)
from services.context_builder import build_initial_message
from services.mcp_service import (
    default_pool_paths,
    read_mcp_pool,
    resolve_allowed_servers,
)
from services.resume_service import (
    build_resume_prompt,
    claim_next_resume_attempt,
    clear_resume_pending,
    mark_resume_pending,
)
from services.run_driver import schedule_run_completion
from services.scheduler_service import claim_next_queued_agent, claim_slot_or_queue
from services.session_rotation_service import rotate_session
from services.worktree_service import ensure_task_worktree

logger = logging.getLogger(__name__)

_DIRECT_MERGE_LOCK = asyncio.Lock()


@dataclass
class TaskRuntimePolicy:
    max_concurrent_agents: int
    base_branch: str = "main"
    merge_type: MergeType = MergeType.DIRECT
    target_branch: str = "main"


async def create_task(
    db, title: str, description: str | None = None, priority: TaskPriority = TaskPriority.MEDIUM
) -> Task:
    task = Task(id=uuid.uuid4(), title=title, description=description, priority=priority)
    db.add(task)
    await commit(db)
    return task


async def assign_task(db, runtime_service: RuntimeService, repo_root: Path, task: Task, agent: Agent, policy: TaskRuntimePolicy) -> Task:
    require_assignable(task, agent)
    task.assignee_id = agent.id
    task.status = TaskStatus.IN_PROGRESS
    task.started_at = utcnow()
    agent.current_task_id = task.id
    if await claim_slot_or_queue(db, agent, policy.max_concurrent_agents):
        await start_agent_on_task(db, runtime_service, repo_root, agent, task, policy)
    return task


def require_assignable(task: Task, agent: Agent) -> None:
    """A repeat assignment must not spawn a second runtime for the same worktree (README Rule 5: one primary task per agent), and a slot-count that only ever counts distinct WORKING agents can't catch that on its own."""
    if task.status != TaskStatus.BACKLOG:
        raise ValueError(f"task {task.id} is not assignable (status={task.status.value})")
    if not agent.active:
        raise ValueError(f"agent {agent.id} is not active")
    if agent.status != AgentStatus.IDLE:
        raise ValueError(f"agent {agent.id} is not idle (status={agent.status.value})")


async def start_agent_on_task(db, runtime_service: RuntimeService, repo_root: Path, agent: Agent, task: Task, policy: TaskRuntimePolicy) -> None:
    """Assumes the caller already claimed agent's WORKING slot; only spawns and hands the run to a background driver."""
    task_worktree = await ensure_task_worktree(db, repo_root, task, policy.base_branch)
    allowed_servers = await resolve_agent_mcp_servers(db, repo_root, agent)
    message = await build_initial_message(db, agent, task, repo_root, allowed_servers)
    run = await runtime_service.spawn(agent, task_worktree, allowed_servers, message)
    schedule_run_completion(runtime_service, repo_root, agent.id, task.id, task_worktree.id, run.id, policy)


async def resolve_agent_mcp_servers(db, repo_root: Path, agent: Agent) -> list[McpServerRef]:
    pool = read_mcp_pool(default_pool_paths(repo_root))
    return await resolve_allowed_servers(db, agent.id, pool)


async def finish_task_run(db, runtime_service: RuntimeService, repo_root: Path, agent: Agent, task: Task, task_worktree: TaskWorktree, run: ExecutionRun, policy: TaskRuntimePolicy) -> None:
    if run.status == RunStatus.COMPLETED:
        await land_or_block(db, agent, task, task_worktree, repo_root, policy)
    elif run.status == RunStatus.INTERRUPTED:
        await handle_interrupted_run(db, runtime_service, repo_root, agent, task, task_worktree, run, policy)
    else:
        await fail_task(db, agent, task, run)
    await promote_next_queued_agent(db, runtime_service, repo_root, policy)


async def handle_interrupted_run(db, runtime_service: RuntimeService, repo_root: Path, agent: Agent, task: Task, task_worktree: TaskWorktree, run: ExecutionRun, policy: TaskRuntimePolicy) -> None:
    """Track B2: the backend went away before this run's outcome was known, so give the same session up to three resume attempts before treating it as a real failure."""
    agent_session = await db.get(AgentSession, run.agent_session_id)
    await mark_resume_pending(db, agent_session, await build_resume_prompt(db, agent_session))
    if not await try_resume_agent_session(db, runtime_service, repo_root, agent, task, task_worktree, agent_session, policy):
        await clear_resume_pending(db, agent_session)
        await fail_task(db, agent, task, run)


async def try_resume_agent_session(db, runtime_service: RuntimeService, repo_root: Path, agent: Agent, task: Task, task_worktree: TaskWorktree, agent_session: AgentSession, policy: TaskRuntimePolicy) -> bool:
    """Claim-before-spawn (B2.2), capped at 3 attempts: counting execution runs would miss an attempt that failed before a row ever existed."""
    if not await claim_next_resume_attempt(db, agent_session.id):
        return False
    resumed = await attempt_resume_spawn(db, runtime_service, repo_root, agent, task, task_worktree, agent_session, policy)
    if resumed:
        await clear_resume_pending(db, agent_session)
    return resumed


async def attempt_resume_spawn(db, runtime_service: RuntimeService, repo_root: Path, agent: Agent, task: Task, task_worktree: TaskWorktree, agent_session: AgentSession, policy: TaskRuntimePolicy) -> bool:
    try:
        if agent_session.claude_session_id:
            return await resume_with_session_id(db, runtime_service, repo_root, agent, task, task_worktree, agent_session, policy)
        return await resume_from_checkpoint(db, runtime_service, repo_root, agent, task, task_worktree, agent_session, policy)
    except Exception:
        logger.exception("resume attempt failed for agent session %s", agent_session.id)
        return False


async def resume_with_session_id(db, runtime_service: RuntimeService, repo_root: Path, agent: Agent, task: Task, task_worktree: TaskWorktree, agent_session: AgentSession, policy: TaskRuntimePolicy) -> bool:
    allowed_servers = await resolve_agent_mcp_servers(db, repo_root, agent)
    run = await runtime_service.resume(agent, agent_session, task_worktree, allowed_servers, agent_session.resume_prompt or "")
    schedule_run_completion(runtime_service, repo_root, agent.id, task.id, task_worktree.id, run.id, policy)
    return True


async def resume_from_checkpoint(db, runtime_service: RuntimeService, repo_root: Path, agent: Agent, task: Task, task_worktree: TaskWorktree, agent_session: AgentSession, policy: TaskRuntimePolicy) -> bool:
    """No claude_session_id survived the crash (Phase 0.2's stdin loss, or a crash before system/init): fall back to a fresh session seeded with the newest unused checkpoint, the same pattern session_rotation_service already uses for a deliberate rotation (B2.7)."""
    checkpoint = await find_latest_unused_checkpoint(db, agent.id, task.id)
    if checkpoint is None:
        return False
    allowed_servers = await resolve_agent_mcp_servers(db, repo_root, agent)
    await rotate_session(db, runtime_service, repo_root, agent, task, task_worktree, agent_session, checkpoint, allowed_servers, policy)
    return True


async def land_or_block(db, agent: Agent, task: Task, task_worktree: TaskWorktree, repo_root: Path, policy: TaskRuntimePolicy) -> None:
    try:
        await land_task(db, agent, task, task_worktree, repo_root, policy)
    except Exception as error:  # noqa: BLE001 - a landing failure must block the task, not vanish in a background task
        await block_on_landing_failure(db, agent, task, error)
        return
    await release_agent(db, agent)


async def land_task(db, agent: Agent, task: Task, task_worktree: TaskWorktree, repo_root: Path, policy: TaskRuntimePolicy) -> TaskMerge:
    path = Path(task_worktree.path)
    landed_sha = await worktree_ops.commit_worktree(path, f"{task.title}\n\nAgent Office task {task.id}")
    if policy.merge_type == MergeType.PR:
        await worktree_ops.push_worktree(path, task_worktree.branch)
    merge = await record_landed_merge(db, task, task_worktree, repo_root, policy)
    await extract_completion_memories_safely(db, agent, task, task_worktree.branch, landed_sha)
    return merge


async def record_landed_merge(db, task: Task, task_worktree: TaskWorktree, repo_root: Path, policy: TaskRuntimePolicy) -> TaskMerge:
    merge = await record_merge(task, task_worktree, repo_root, policy)
    db.add(merge)
    task.status = TaskStatus.DONE
    task.completed_at = utcnow()
    await commit(db)
    bus.publish(TASK_COMPLETED, serialize(task))
    return merge


async def extract_completion_memories_safely(db, agent: Agent, task: Task, branch: str, landed_sha: str | None) -> None:
    """A1.5: a broken extraction must not undo a landing that already succeeded above."""
    try:
        await extract_memories_on_task_completion(db, agent.id, task.id, task.title, branch, landed_sha)
    except Exception:
        logger.exception("memory extraction failed for task %s", task.id)


async def record_merge(task: Task, task_worktree: TaskWorktree, repo_root: Path, policy: TaskRuntimePolicy) -> TaskMerge:
    if policy.merge_type == MergeType.PR:
        return await record_pr_merge(task, task_worktree, policy.target_branch)
    return await record_direct_merge(task, task_worktree, repo_root, policy.target_branch)


async def record_pr_merge(task: Task, task_worktree: TaskWorktree, target_branch: str) -> TaskMerge:
    body = f"Landed by Agent Office task {task.id}."
    head = task_worktree.branch
    number, url = await landing.open_pull_request(Path(task_worktree.path), target_branch, head, task.title, body)
    return TaskMerge(
        id=uuid.uuid4(), task_id=task.id, type=MergeType.PR, target_branch=target_branch, pr_number=number, pr_url=url, pr_status=PrStatus.OPEN
    )


async def record_direct_merge(task: Task, task_worktree: TaskWorktree, repo_root: Path, target_branch: str) -> TaskMerge:
    """Serialized: repo_root is one shared checkout, so two landings can't merge into it at the same time."""
    async with _DIRECT_MERGE_LOCK:
        merge_commit = await landing.merge_direct(repo_root, task_worktree.branch, target_branch)
    return TaskMerge(id=uuid.uuid4(), task_id=task.id, type=MergeType.DIRECT, target_branch=target_branch, merge_commit=merge_commit)


async def block_on_landing_failure(db, agent: Agent, task: Task, error: Exception) -> AttentionEvent:
    return await block_task(db, agent, task, f"Landing {task.title} failed", str(error))


async def fail_task(db, agent: Agent, task: Task, run: ExecutionRun) -> AttentionEvent:
    title = f"{agent.name} failed {task.title}"
    message = f"Execution run {run.id} exited with code {run.exit_code}."
    return await block_task(db, agent, task, title, message)


async def block_task(db, agent: Agent, task: Task, title: str, message: str) -> AttentionEvent:
    task.status = TaskStatus.BLOCKED
    agent.status = AgentStatus.BLOCKED
    agent.needs_attention = True
    event = AttentionEvent(id=uuid.uuid4(), type=AttentionType.TASK_FAILED, agent_id=agent.id, task_id=task.id, title=title, message=message)
    db.add(event)
    await commit(db)
    bus.publish(TASK_BLOCKED, serialize(task))
    bus.publish(AGENT_STATUS_CHANGED, serialize(agent))
    bus.publish(ATTENTION_CREATED, serialize(event))
    return event


async def release_agent(db, agent: Agent) -> None:
    agent.status = AgentStatus.IDLE
    agent.current_task_id = None
    await commit(db)
    bus.publish(AGENT_STATUS_CHANGED, serialize(agent))


async def promote_next_queued_agent(db, runtime_service: RuntimeService, repo_root: Path, policy: TaskRuntimePolicy) -> Agent | None:
    next_agent = await claim_next_queued_agent(db, policy.max_concurrent_agents)
    if next_agent is None:
        return None
    task = await db.get(Task, next_agent.current_task_id)
    await start_agent_on_task(db, runtime_service, repo_root, next_agent, task, policy)
    return next_agent


async def list_tasks(db) -> list[Task]:
    return list((await db.execute(select(Task).order_by(Task.created_at))).scalars())
