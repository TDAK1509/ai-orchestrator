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
    ATTENTION_RESOLVED,
    TASK_BLOCKED,
    TASK_COMPLETED,
    TASK_UPDATED,
)
from models.agent import Agent, AgentStatus
from models.attention import AttentionEvent, AttentionType
from models.base import utcnow
from models.merge import MergeType, PrStatus, TaskMerge
from models.session import AgentSession, ExecutionRun, RunStatus
from models.task import Task, TaskPriority, TaskStatus
from models.worktree import TaskWorktree, WorktreeStatus
from runtime import landing
from runtime import worktree as worktree_ops
from runtime.mcp_config import McpServerRef
from runtime.runtime_service import RuntimeService
from serialization import serialize
from services.agent_service import (
    find_running_run_for_agent,
    reject_null_required_field,
    stop_active_runtime,
)
from services.checkpoint_service import (
    extract_memories_on_task_completion,
    find_latest_unused_checkpoint,
)
from services.context_builder import build_initial_message
from services.decision_service import cancel_pending_decisions_for_task
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
from services.worktree_service import (
    ensure_task_worktree,
    find_task_worktree,
    remove_task_worktree,
    resolve_base_branch,
    resolve_repo_root,
    resolve_task_repository,
)

logger = logging.getLogger(__name__)

_DIRECT_MERGE_LOCK = asyncio.Lock()


@dataclass
class TaskRuntimePolicy:
    max_concurrent_agents: int
    # allow-comment: a repository with no remote falls back to MergeType.DIRECT regardless of this preference -- see resolve_merge_type.
    merge_type: MergeType = MergeType.PR


async def create_task(
    db, title: str, description: str | None = None, priority: TaskPriority = TaskPriority.MEDIUM,
    repository_id: uuid.UUID | None = None, created_by_agent_id: uuid.UUID | None = None,
) -> Task:
    task = Task(
        id=uuid.uuid4(), title=title, description=description, priority=priority,
        repository_id=repository_id, created_by_agent_id=created_by_agent_id,
    )
    db.add(task)
    await commit(db)
    return task


async def edit_task(db, task: Task, body, fields_set: set[str]) -> Task:
    await apply_task_edits(db, task, body, fields_set)
    await commit(db)
    return task


async def apply_task_edits(db, task: Task, body, fields_set: set[str]) -> None:
    reject_null_required_field(body, fields_set, "title")
    reject_null_required_field(body, fields_set, "priority")
    reject_null_required_field(body, fields_set, "repository_id")
    if "repository_id" in fields_set and body.repository_id != task.repository_id:
        await require_no_worktree(db, task)
    for field in ("title", "description", "priority", "repository_id"):
        if field in fields_set:
            setattr(task, field, getattr(body, field))


async def require_no_worktree(db, task: Task) -> None:
    """A worktree is already cut from the task's current repository (README 19.3): repointing repository_id out from under it would leave the checkout, its branch and its before_head_commit describing a different repo than the task claims."""
    worktree = await find_task_worktree(db, task.id)
    if worktree is not None:
        raise ValueError(f"task {task.id} already has a worktree ({worktree.path}); repository cannot be changed")


async def archive_task(db, runtime_service: RuntimeService, task: Task) -> Task:
    """Archive, never delete (six tables FK tasks.id): the task and its worktree row both survive, marked retired instead of gone."""
    agent, resolved_events = await teardown_task_for_archive(db, runtime_service, task)
    task.status = TaskStatus.ARCHIVED
    await commit(db)
    publish_task_archived(task, agent, resolved_events)
    return task


async def teardown_task_for_archive(db, runtime_service: RuntimeService, task: Task) -> tuple[Agent | None, list[AttentionEvent]]:
    await cancel_pending_decisions_for_task(db, task.id)
    agent = await stop_and_release_task_agent(db, runtime_service, task)
    await remove_task_worktree(db, task)
    resolved_events = await resolve_open_task_attention(db, task.id)
    return agent, resolved_events


def publish_task_archived(task: Task, agent: Agent | None, resolved_events: list[AttentionEvent]) -> None:
    bus.publish(TASK_UPDATED, serialize(task))
    if agent is not None:
        bus.publish(AGENT_STATUS_CHANGED, serialize(agent))
    for event in resolved_events:
        bus.publish(ATTENTION_RESOLVED, serialize(event))


async def resolve_open_task_attention(db, task_id: uuid.UUID) -> list[AttentionEvent]:
    """codex: an archived task must not leave its attention row unresolved forever -- the decision case above already resolves its own event, this covers a plain TASK_FAILED/AGENT_BLOCKED one."""
    query = select(AttentionEvent).where(AttentionEvent.task_id == task_id, AttentionEvent.resolved.is_(False))
    events = list((await db.execute(query)).scalars())
    for event in events:
        event.resolved = True
        event.resolved_at = utcnow()
    return events


async def stop_and_release_task_agent(db, runtime_service: RuntimeService, task: Task) -> Agent | None:
    if task.assignee_id is None:
        return None
    agent = await db.get(Agent, task.assignee_id)
    if agent is None or agent.current_task_id != task.id:
        return agent
    await stop_active_runtime(db, runtime_service, agent)
    agent.status = AgentStatus.IDLE
    agent.current_task_id = None
    agent.needs_attention = False
    return agent


async def assign_task(db, runtime_service: RuntimeService, repo_root: Path, task: Task, agent: Agent, policy: TaskRuntimePolicy) -> Task:
    await require_assignable(db, task, agent, policy)
    task.assignee_id = agent.id
    task.status = TaskStatus.IN_PROGRESS
    task.started_at = utcnow()
    agent.current_task_id = task.id
    if await claim_slot_or_queue(db, agent, policy.max_concurrent_agents):
        await start_or_revert_assignment(db, runtime_service, repo_root, agent, task, policy)
    return task


async def start_or_revert_assignment(db, runtime_service: RuntimeService, repo_root: Path, agent: Agent, task: Task, policy: TaskRuntimePolicy) -> None:
    """PR 1: the pre-flight fetch does not guarantee the worktree's own fetch (a queued agent can be promoted long after) also succeeds -- a failure here must not leave the task IN_PROGRESS and the agent WORKING with no run behind either of them."""
    try:
        await start_agent_on_task(db, runtime_service, repo_root, agent, task, policy)
    except Exception:
        await revert_failed_assignment(db, agent, task)
        raise


async def revert_failed_assignment(db, agent: Agent, task: Task) -> None:
    task.status = TaskStatus.BACKLOG
    task.assignee_id = None
    task.started_at = None
    agent.current_task_id = None
    agent.status = AgentStatus.IDLE
    await commit(db)


async def require_assignable(db, task: Task, agent: Agent, policy: TaskRuntimePolicy) -> None:
    """A repeat assignment must not spawn a second runtime for the same worktree (README Rule 5: one primary task per agent), and a slot-count that only ever counts distinct WORKING agents can't catch that on its own."""
    if task.status != TaskStatus.BACKLOG:
        raise ValueError(f"task {task.id} is not assignable (status={task.status.value})")
    if not agent.active:
        raise ValueError(f"agent {agent.id} is not active")
    if agent.status != AgentStatus.IDLE:
        raise ValueError(f"agent {agent.id} is not idle (status={agent.status.value})")
    await require_repo_ready_for_assignment(db, task, policy)


async def require_repo_ready_for_assignment(db, task: Task, policy: TaskRuntimePolicy) -> None:
    """PR 1: fetches the repository's default ref before anything else runs, so a stale base or a dead network fails assignment immediately instead of silently handing the agent old code."""
    repository = await resolve_task_repository(db, task)
    repo_root = resolve_repo_root(repository)
    await require_fresh_base(repo_root, repository.default_target_branch)
    if await resolve_merge_type(repo_root, policy.merge_type) == MergeType.DIRECT:
        await require_direct_merge_ready(repo_root, repository.default_target_branch)


async def require_direct_merge_ready(repo_root: Path, default_ref: str) -> None:
    """PR 4: the same branch check landing makes at merge time (runtime.landing.require_clean_checkout_of), run here before any work starts -- only reached when resolve_merge_type says this repository lands directly into its checkout. Dirtiness is transient, so it only warns; landing is still the one that refuses on it."""
    target_branch = await worktree_ops.local_branch_name_for(repo_root, default_ref)
    current_branch = await worktree_ops.read_current_branch(repo_root)
    if current_branch != target_branch:
        raise ValueError(f"{repo_root} is on {current_branch!r}, expected {target_branch!r}")
    if await worktree_ops.has_staged_changes(repo_root):
        logger.warning("repository %s is dirty (expected clean on %r); assignment allowed, landing will refuse until it is clean", repo_root, target_branch)


async def require_fresh_base(repo_root: Path, target_ref: str) -> None:
    """PR 1: a stale base is worse than a clear failure -- a fetch failure here (network down, remote gone) blocks assignment with the git error instead of silently cutting the worktree from whatever was last pulled."""
    try:
        await worktree_ops.resolve_worktree_base(repo_root, target_ref)
    except worktree_ops.GitCommandError as error:
        raise ValueError(f"could not fetch {target_ref} for {repo_root}: {error}") from error


async def resolve_merge_type(repo_root: Path, preferred: MergeType) -> MergeType:
    """PR 2: `gh pr create` only works against a GitHub remote -- a repository with none, or one whose `origin` points elsewhere (GitLab, Bitbucket, a local bare repo), lands directly into its checkout instead, regardless of the workspace's preferred merge type."""
    if preferred == MergeType.DIRECT:
        return MergeType.DIRECT
    return MergeType.PR if await worktree_ops.has_github_remote(repo_root, "origin") else MergeType.DIRECT


async def start_agent_on_task(db, runtime_service: RuntimeService, repo_root: Path, agent: Agent, task: Task, policy: TaskRuntimePolicy) -> None:
    """Assumes the caller already claimed agent's WORKING slot; only spawns and hands the run to a background driver."""
    task_repo_root, base_branch = await resolve_task_repo_context(db, task)
    task_worktree = await ensure_task_worktree(db, task_repo_root, task, base_branch)
    allowed_servers = await resolve_agent_mcp_servers(db, task_repo_root, agent)
    message = await build_initial_message(db, agent, task, task_repo_root, allowed_servers)
    run = await runtime_service.spawn(agent, task_worktree, allowed_servers, message)
    schedule_run_completion(runtime_service, repo_root, agent.id, task.id, task_worktree.id, run.id, policy)


async def resolve_task_repo_context(db, task: Task) -> tuple[Path, str]:
    """A2/PR 4: every task has a repository (README 14) -- resolve its checkout path and default branch, no workspace-default fallback left."""
    repository = await resolve_task_repository(db, task)
    return resolve_repo_root(repository), resolve_base_branch(repository)


async def resolve_agent_mcp_servers(db, repo_root: Path, agent: Agent) -> list[McpServerRef]:
    pool = read_mcp_pool(default_pool_paths(repo_root))
    return await resolve_allowed_servers(db, agent.id, pool)


async def finish_task_run(db, runtime_service: RuntimeService, repo_root: Path, agent: Agent, task: Task, task_worktree: TaskWorktree, run: ExecutionRun, policy: TaskRuntimePolicy) -> None:
    """A run only lands, fails or crash-resumes while its task is actively IN_PROGRESS (codex: a PR 1 chat message can resume a DONE or ARCHIVED task's last session, and archiving races this driver via a run it already killed -- neither should re-land, re-fail or re-block a task that isn't being worked)."""
    if task.status == TaskStatus.IN_PROGRESS:
        await finish_in_progress_run(db, runtime_service, repo_root, agent, task, task_worktree, run, policy)
    await promote_next_queued_agent(db, runtime_service, repo_root, policy)


async def finish_in_progress_run(db, runtime_service: RuntimeService, repo_root: Path, agent: Agent, task: Task, task_worktree: TaskWorktree, run: ExecutionRun, policy: TaskRuntimePolicy) -> None:
    if run.status == RunStatus.COMPLETED:
        await land_or_block(db, agent, task, task_worktree, policy)
    elif run.status in (RunStatus.INTERRUPTED, RunStatus.KILLED):
        # allow-comment: B2's deliberate Stop ends the same way an unplanned interruption does (codex P1) -- the process is gone either way, and the task needs the same up-to-3-attempt resume, not an immediate permanent failure.
        await handle_interrupted_run(db, runtime_service, repo_root, agent, task, task_worktree, run, policy)
    else:
        await fail_task(db, agent, task, run)


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
        return await resume_from_checkpoint(db, runtime_service, agent, task, task_worktree, agent_session, policy)
    except Exception:
        logger.exception("resume attempt failed for agent session %s", agent_session.id)
        return False


async def resume_with_session_id(db, runtime_service: RuntimeService, repo_root: Path, agent: Agent, task: Task, task_worktree: TaskWorktree, agent_session: AgentSession, policy: TaskRuntimePolicy) -> bool:
    await resume_agent_session(db, runtime_service, repo_root, agent, task, task_worktree, agent_session, policy, agent_session.resume_prompt or "")
    return True


async def resume_agent_session(db, runtime_service: RuntimeService, repo_root: Path, agent: Agent, task: Task, task_worktree: TaskWorktree, agent_session: AgentSession, policy: TaskRuntimePolicy, prompt_text: str) -> ExecutionRun:
    """Shared by the crash-resume loop above, a human message to the agent (PR 1), and a task retry (PR 2) -- only prompt_text differs between callers."""
    task_repo_root, _ = await resolve_task_repo_context(db, task)
    allowed_servers = await resolve_agent_mcp_servers(db, task_repo_root, agent)
    run = await runtime_service.resume(agent, agent_session, task_worktree, allowed_servers, prompt_text)
    schedule_run_completion(runtime_service, repo_root, agent.id, task.id, task_worktree.id, run.id, policy)
    return run


async def resume_from_checkpoint(db, runtime_service: RuntimeService, agent: Agent, task: Task, task_worktree: TaskWorktree, agent_session: AgentSession, policy: TaskRuntimePolicy) -> bool:
    """No claude_session_id survived the crash (Phase 0.2's stdin loss, or a crash before system/init): fall back to a fresh session seeded with the newest unused checkpoint, the same pattern session_rotation_service already uses for a deliberate rotation (B2.7)."""
    checkpoint = await find_latest_unused_checkpoint(db, agent.id, task.id)
    if checkpoint is None:
        return False
    task_repo_root, _ = await resolve_task_repo_context(db, task)
    allowed_servers = await resolve_agent_mcp_servers(db, task_repo_root, agent)
    await rotate_session(db, runtime_service, task_repo_root, agent, task, task_worktree, agent_session, checkpoint, allowed_servers, policy)
    return True


async def land_or_block(db, agent: Agent, task: Task, task_worktree: TaskWorktree, policy: TaskRuntimePolicy) -> None:
    try:
        await land_task(db, agent, task, task_worktree, policy)
    except Exception as error:  # noqa: BLE001 - a landing failure must block the task, not vanish in a background task
        await block_on_landing_failure(db, agent, task, error)
        return
    await release_agent(db, agent)


async def land_task(db, agent: Agent, task: Task, task_worktree: TaskWorktree, policy: TaskRuntimePolicy) -> TaskMerge:
    task_repo_root, default_ref = await resolve_task_repo_context(db, task)
    target_branch = await worktree_ops.local_branch_name_for(task_repo_root, default_ref)
    merge_type = await resolve_merge_type(task_repo_root, policy.merge_type)
    path = Path(task_worktree.path)
    landed_sha = await commit_task_worktree(path, f"{task.title}\n\nAgent Office task {task.id}")
    if merge_type == MergeType.PR:
        await worktree_ops.push_worktree(path, task_worktree.branch)
    merge = await record_landed_merge(db, task, task_worktree, task_repo_root, target_branch, merge_type)
    await extract_completion_memories_safely(db, agent, task, task_worktree.branch, landed_sha)
    return merge


async def commit_task_worktree(path: Path, message: str) -> str | None:
    """PR 2: land only what the task produced -- never `add -A`, which would sweep in scratch and half-finished edits the agent left behind."""
    paths = await worktree_ops.resolve_paths_to_commit(path)
    return await worktree_ops.commit_paths(path, paths, message)


async def record_landed_merge(db, task: Task, task_worktree: TaskWorktree, repo_root: Path, target_branch: str, merge_type: MergeType) -> TaskMerge:
    merge = await record_merge(task, task_worktree, repo_root, target_branch, merge_type)
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


async def record_merge(task: Task, task_worktree: TaskWorktree, repo_root: Path, target_branch: str, merge_type: MergeType) -> TaskMerge:
    if merge_type == MergeType.PR:
        return await record_pr_merge(task, task_worktree, target_branch)
    return await record_direct_merge(task, task_worktree, repo_root, target_branch)


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


async def send_message_to_agent(db, runtime_service: RuntimeService, repo_root: Path, agent: Agent, content: str, policy: TaskRuntimePolicy) -> ExecutionRun:
    """PR 1: a human message resumes the agent's own last session -- no new runtime mechanics, just resume_agent_session with a human's text instead of a resume prompt."""
    await require_messageable(db, agent)
    task_worktree, agent_session = await find_message_target(db, agent)
    if agent_session is None:
        raise ValueError(f"agent {agent.id} has no session to message")
    if task_worktree.status != WorktreeStatus.ACTIVE:
        raise ValueError(f"agent {agent.id}'s last session worktree was removed (its task was archived)")
    task = await db.get(Task, task_worktree.task_id)
    return await resume_agent_session(db, runtime_service, repo_root, agent, task, task_worktree, agent_session, policy, content)


async def find_message_target(db, agent: Agent) -> tuple[TaskWorktree | None, AgentSession | None]:
    """codex: a QUEUED agent has a current_task_id but no worktree yet (it's still waiting for a slot) -- messaging must target that current task's own session, never fall back to an unrelated older one, so a QUEUED agent finds nothing rather than resuming the wrong task."""
    if agent.current_task_id is None:
        session = await find_latest_agent_session(db, agent.id)
        return (await db.get(TaskWorktree, session.task_worktree_id)) if session else None, session
    task_worktree = await find_task_worktree(db, agent.current_task_id)
    if task_worktree is None:
        return None, None
    return task_worktree, await find_latest_agent_session(db, agent.id, task_worktree.id)


async def require_messageable(db, agent: Agent) -> None:
    """Refuses a run already RUNNING for the agent (README: two processes resuming one Claude session concurrently is a foreign-writer hazard, self-inflicted)."""
    if not agent.active:
        raise ValueError(f"agent {agent.id} is not active")
    if await find_running_run_for_agent(db, agent) is not None:
        raise ValueError(f"agent {agent.id} already has a run in progress")


async def find_latest_agent_session(db, agent_id: uuid.UUID, task_worktree_id: uuid.UUID | None = None) -> AgentSession | None:
    query = select(AgentSession).where(AgentSession.agent_id == agent_id, AgentSession.task_worktree_id.is_not(None))
    if task_worktree_id is not None:
        query = query.where(AgentSession.task_worktree_id == task_worktree_id)
    query = query.order_by(AgentSession.created_at.desc()).limit(1)
    return (await db.execute(query)).scalars().first()


async def retry_task(db, runtime_service: RuntimeService, repo_root: Path, task: Task, policy: TaskRuntimePolicy) -> Task:
    """PR 2: resumes the agent with the reason it was blocked, so it hears why it was woken instead of guessing (README: retry resumes the agent, it does not merely re-run landing)."""
    agent, task_worktree, agent_session = await load_retry_targets(db, task)
    attention_event = await find_open_task_attention(db, task.id)
    prompt_text = unblock_task_for_retry(task, agent, attention_event)
    await commit(db)
    publish_task_retry(task, agent, attention_event)
    await resume_agent_session(db, runtime_service, repo_root, agent, task, task_worktree, agent_session, policy, prompt_text)
    return task


async def load_retry_targets(db, task: Task) -> tuple[Agent, TaskWorktree, AgentSession]:
    agent = await require_retryable(db, task)
    task_worktree = await find_task_worktree(db, task.id)
    if task_worktree is None:
        raise ValueError(f"task {task.id} has no worktree to resume")
    agent_session = await find_latest_agent_session(db, agent.id, task_worktree.id)
    if agent_session is None:
        raise ValueError(f"task {task.id} has no session to resume")
    return agent, task_worktree, agent_session


async def require_retryable(db, task: Task) -> Agent:
    """A decision-blocked task's process is still RUNNING (ask_human parks it, it never exits) -- retry must refuse that the same way messaging refuses a second resume onto a live process (codex critical)."""
    if task.status != TaskStatus.BLOCKED:
        raise ValueError(f"task {task.id} is not blocked (status={task.status.value})")
    agent = await db.get(Agent, task.assignee_id) if task.assignee_id else None
    if agent is None:
        raise ValueError(f"task {task.id} has no assignee to retry")
    if agent.status != AgentStatus.BLOCKED:
        raise ValueError(f"agent {agent.id} is not blocked (status={agent.status.value})")
    if await find_running_run_for_agent(db, agent) is not None:
        raise ValueError(f"agent {agent.id} already has a run in progress")
    return agent


async def find_open_task_attention(db, task_id: uuid.UUID) -> AttentionEvent | None:
    """Excludes a pending decision (decision_request_id set): that reopens through /decisions/{id}/answer, which already owns unblocking correctly -- retry must not race it."""
    query = (
        select(AttentionEvent)
        .where(AttentionEvent.task_id == task_id, AttentionEvent.resolved.is_(False), AttentionEvent.decision_request_id.is_(None))
        .order_by(AttentionEvent.created_at.desc())
        .limit(1)
    )
    return (await db.execute(query)).scalars().first()


def unblock_task_for_retry(task: Task, agent: Agent, attention_event: AttentionEvent | None) -> str:
    task.status = TaskStatus.IN_PROGRESS
    agent.status = AgentStatus.WORKING
    agent.needs_attention = False
    if attention_event is None:
        return "You were blocked; a human retried this task without a specific message. Please continue."
    attention_event.resolved = True
    attention_event.resolved_at = utcnow()
    return f"{attention_event.title}: {attention_event.message}"


def publish_task_retry(task: Task, agent: Agent, attention_event: AttentionEvent | None) -> None:
    bus.publish(TASK_UPDATED, serialize(task))
    bus.publish(AGENT_STATUS_CHANGED, serialize(agent))
    if attention_event is not None:
        bus.publish(ATTENTION_RESOLVED, serialize(attention_event))


async def list_tasks(db) -> list[Task]:
    query = select(Task).where(Task.status != TaskStatus.ARCHIVED).order_by(Task.created_at)
    return list((await db.execute(query)).scalars())
