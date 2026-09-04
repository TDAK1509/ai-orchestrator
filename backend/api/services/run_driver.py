import asyncio
import uuid

from events.bus import bus
from events.schema import RUNTIME_EVENT
from models.agent import Agent
from models.session import ExecutionRun
from models.task import Task
from models.worktree import TaskWorktree
from runtime.runtime_service import RuntimeService
from runtime.stream_parser import DomainEvent

# allow-comment: kept separate from task_service (which needs to schedule a resumed run without importing back from session_rotation_service, and vice versa): a leaf module both can depend on, so neither imports the other.
_BACKGROUND_RUNS: dict[uuid.UUID, asyncio.Task] = {}


def schedule_run_completion(runtime_service, repo_root, agent_id, task_id, task_worktree_id, run_id, policy) -> None:
    """One worker owns one process for its whole life (README 31.1): this is that worker, driving the run to a finished task on its own session, never the caller's. Tracked by run_id (Phase 0.6) so a shutdown can mark each one killed before draining it."""
    coroutine = drive_run_to_completion(runtime_service, repo_root, agent_id, task_id, task_worktree_id, run_id, policy)
    background_task = asyncio.create_task(coroutine)
    _BACKGROUND_RUNS[run_id] = background_task
    background_task.add_done_callback(lambda _task: _BACKGROUND_RUNS.pop(run_id, None))


async def drive_run_to_completion(runtime_service, repo_root, agent_id, task_id, task_worktree_id, run_id, policy) -> None:
    async for event in runtime_service.stream_events(run_id):
        publish_runtime_event(agent_id, task_id, run_id, event)
    async with runtime_service.session_factory() as db:
        agent, task, task_worktree, run = await load_run_context(db, agent_id, task_id, task_worktree_id, run_id)
        await finish_run(db, runtime_service, repo_root, agent, task, task_worktree, run, policy)


async def finish_run(db, runtime_service, repo_root, agent, task, task_worktree, run, policy) -> None:
    # allow-comment: deferred import breaks the cycle -- task_service imports schedule_run_completion from this module at load time, so this module cannot import task_service at load time too.
    from services.task_service import finish_task_run

    await finish_task_run(db, runtime_service, repo_root, agent, task, task_worktree, run, policy)


def publish_runtime_event(agent_id, task_id, run_id, event: DomainEvent) -> None:
    payload = {
        "agentId": str(agent_id), "taskId": str(task_id), "runId": str(run_id),
        "kind": event.kind, "text": event.text, "toolName": event.tool_name,
        "filePath": event.file_path, "exitResult": event.exit_result,
    }
    bus.publish(RUNTIME_EVENT, payload)


async def load_run_context(db, agent_id, task_id, task_worktree_id, run_id):
    """The run may have started long before this coroutine resumes (stream_events blocks on the process): reload state fresh instead of trusting stale objects from before the spawn."""
    agent = await db.get(Agent, agent_id)
    task = await db.get(Task, task_id)
    task_worktree = await db.get(TaskWorktree, task_worktree_id)
    run = await db.get(ExecutionRun, run_id)
    return agent, task, task_worktree, run


async def shutdown_background_runs(runtime_service: RuntimeService) -> None:
    """A background run's own coroutine finishes on its own once kill_run stops its process (a normal stream EOF, not a cancellation): cancelling stream_events mid-line would instead need a bug-prone GeneratorExit path through an async generator."""
    tasks = dict(_BACKGROUND_RUNS)
    for run_id in tasks:
        await runtime_service.kill_run(run_id)
    await _await_or_cancel(tasks)


async def _await_or_cancel(tasks: dict[uuid.UUID, asyncio.Task], timeout_seconds: float = 15.0) -> None:
    try:
        await asyncio.wait_for(asyncio.gather(*tasks.values(), return_exceptions=True), timeout=timeout_seconds)
    except TimeoutError:
        for task in tasks.values():
            task.cancel()
