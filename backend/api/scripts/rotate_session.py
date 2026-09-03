#!/usr/bin/env python3
"""Manually triggers session rotation from a saved checkpoint (README 17.5). No automatic trigger exists yet -- there's no tokenizer to decide "too large" on its own."""
import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import build_engine, build_session_factory
from models.agent import Agent
from models.checkpoint import AgentCheckpoint
from models.session import AgentSession, ExecutionRun, RunStatus
from models.task import Task
from runtime.runtime_service import RuntimeService, RuntimeSettings
from services.session_rotation_service import rotate_session
from services.task_service import TaskRuntimePolicy, resolve_agent_mcp_servers
from services.worktree_service import find_task_worktree

POLL_INTERVAL_SECONDS = 1.0


async def main() -> None:
    args = parse_args()
    engine = build_engine()
    session_factory = build_session_factory(engine)
    service = RuntimeService(session_factory, RuntimeSettings())
    async with session_factory() as db:
        policy = TaskRuntimePolicy(max_concurrent_agents=args.max_concurrent_agents)
        run = await rotate_from_checkpoint(db, service, Path(args.repo_root), uuid.UUID(args.checkpoint_id), policy)
        print(f"rotated: new run {run.id}, waiting for it to finish...")
        status = await wait_for_completion(db, run.id)
        print(f"new run finished with status {status.value}")
    await engine.dispose()


async def rotate_from_checkpoint(db, runtime_service: RuntimeService, repo_root: Path, checkpoint_id: uuid.UUID, policy: TaskRuntimePolicy) -> ExecutionRun:
    checkpoint = await db.get(AgentCheckpoint, checkpoint_id)
    agent = await db.get(Agent, checkpoint.agent_id)
    task = await db.get(Task, checkpoint.task_id)
    old_session = await db.get(AgentSession, checkpoint.agent_session_id)
    task_worktree = await find_task_worktree(db, checkpoint.task_id)
    allowed_servers = await resolve_agent_mcp_servers(db, repo_root, agent)
    return await rotate_session(db, runtime_service, repo_root, agent, task, task_worktree, old_session, checkpoint, allowed_servers, policy)


async def wait_for_completion(db, run_id: uuid.UUID) -> RunStatus:
    """The new run is scheduled onto a background task in this process (README 31.1's one worker, one process). If this script exited immediately, that task would be cancelled with it -- so it stays alive and polls instead."""
    while True:
        db.expire_all()
        run = await db.get(ExecutionRun, run_id)
        if run.status != RunStatus.RUNNING:
            return run.status
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-id", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--max-concurrent-agents", type=int, default=1)
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main())
