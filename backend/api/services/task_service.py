import asyncio
import uuid
from dataclasses import dataclass
from pathlib import Path

from models.agent import Agent, AgentStatus
from models.attention import AttentionEvent, AttentionType
from models.base import utcnow
from models.merge import MergeType, PrStatus, TaskMerge
from models.session import ExecutionRun, RunStatus
from models.task import Task, TaskPriority, TaskStatus
from models.worktree import TaskWorktree
from runtime import landing
from runtime import worktree as worktree_ops
from runtime.mcp_config import McpServerRef
from runtime.prompt import build_initial_user_message
from runtime.runtime_service import RuntimeService
from services.mcp_service import (
    default_pool_paths,
    read_mcp_pool,
    resolve_allowed_servers,
)
from services.scheduler_service import claim_next_queued_agent, claim_slot_or_queue
from services.worktree_service import ensure_task_worktree

_DIRECT_MERGE_LOCK = asyncio.Lock()
_BACKGROUND_RUNS: set[asyncio.Task] = set()


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
    await db.commit()
    return task


async def assign_task(db, runtime_service: RuntimeService, repo_root: Path, task: Task, agent: Agent, policy: TaskRuntimePolicy) -> Task:
    task.assignee_id = agent.id
    task.status = TaskStatus.IN_PROGRESS
    task.started_at = utcnow()
    agent.current_task_id = task.id
    if await claim_slot_or_queue(db, agent, policy.max_concurrent_agents):
        await start_agent_on_task(db, runtime_service, repo_root, agent, task, policy)
    return task


async def start_agent_on_task(db, runtime_service: RuntimeService, repo_root: Path, agent: Agent, task: Task, policy: TaskRuntimePolicy) -> None:
    """Assumes the caller already claimed agent's WORKING slot; only spawns and hands the run to a background driver."""
    task_worktree = await ensure_task_worktree(db, repo_root, task, policy.base_branch)
    allowed_servers = await resolve_agent_mcp_servers(db, repo_root, agent)
    run = await runtime_service.spawn(agent, task_worktree, allowed_servers, build_initial_user_message(task))
    schedule_run_completion(db, runtime_service, repo_root, agent, task, task_worktree, run, policy)


async def resolve_agent_mcp_servers(db, repo_root: Path, agent: Agent) -> list[McpServerRef]:
    pool = read_mcp_pool(default_pool_paths(repo_root))
    return await resolve_allowed_servers(db, agent.id, pool)


def schedule_run_completion(db, runtime_service, repo_root, agent, task, task_worktree, run, policy) -> None:
    """One worker owns one process for its whole life (README 31.1): this is that worker, driving the run to a finished task without a caller needing to poll it."""
    coroutine = drive_run_to_completion(db, runtime_service, repo_root, agent, task, task_worktree, run, policy)
    background_task = asyncio.create_task(coroutine)
    _BACKGROUND_RUNS.add(background_task)
    background_task.add_done_callback(_BACKGROUND_RUNS.discard)


async def drive_run_to_completion(db, runtime_service, repo_root, agent, task, task_worktree, run, policy) -> None:
    async for _event in runtime_service.stream_events(run.id):
        pass
    await finish_task_run(db, runtime_service, repo_root, agent, task, task_worktree, run, policy)


async def finish_task_run(db, runtime_service: RuntimeService, repo_root: Path, agent: Agent, task: Task, task_worktree: TaskWorktree, run: ExecutionRun, policy: TaskRuntimePolicy) -> None:
    if run.status == RunStatus.COMPLETED:
        await land_or_block(db, agent, task, task_worktree, repo_root, policy)
    else:
        await fail_task(db, agent, task, run)
    await promote_next_queued_agent(db, runtime_service, repo_root, policy)


async def land_or_block(db, agent: Agent, task: Task, task_worktree: TaskWorktree, repo_root: Path, policy: TaskRuntimePolicy) -> None:
    try:
        await land_task(db, task, task_worktree, repo_root, policy)
    except Exception as error:  # noqa: BLE001 - a landing failure must block the task, not vanish in a background task
        await block_on_landing_failure(db, agent, task, error)
        return
    await release_agent(db, agent)


async def land_task(db, task: Task, task_worktree: TaskWorktree, repo_root: Path, policy: TaskRuntimePolicy) -> TaskMerge:
    path = Path(task_worktree.path)
    await worktree_ops.commit_worktree(path, f"{task.title}\n\nAgent Office task {task.id}")
    if policy.merge_type == MergeType.PR:
        await worktree_ops.push_worktree(path, task_worktree.branch)
    merge = await record_merge(task, task_worktree, repo_root, policy)
    db.add(merge)
    task.status = TaskStatus.DONE
    task.completed_at = utcnow()
    await db.commit()
    return merge


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
    await db.commit()
    return event


async def release_agent(db, agent: Agent) -> None:
    agent.status = AgentStatus.IDLE
    agent.current_task_id = None
    await db.commit()


async def promote_next_queued_agent(db, runtime_service: RuntimeService, repo_root: Path, policy: TaskRuntimePolicy) -> Agent | None:
    next_agent = await claim_next_queued_agent(db, policy.max_concurrent_agents)
    if next_agent is None:
        return None
    task = await db.get(Task, next_agent.current_task_id)
    await start_agent_on_task(db, runtime_service, repo_root, next_agent, task, policy)
    return next_agent
