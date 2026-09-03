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
from models.session import AgentSession
from models.task import Task
from runtime.runtime_service import RuntimeService, RuntimeSettings
from services.session_rotation_service import rotate_session
from services.task_service import resolve_agent_mcp_servers
from services.worktree_service import find_task_worktree


async def main() -> None:
    args = parse_args()
    engine = build_engine()
    session_factory = build_session_factory(engine)
    service = RuntimeService(session_factory, RuntimeSettings())
    async with session_factory() as db:
        run = await rotate_from_checkpoint(db, service, Path(args.repo_root), uuid.UUID(args.checkpoint_id))
    print(f"rotated: new run {run.id}")
    await engine.dispose()


async def rotate_from_checkpoint(db, runtime_service: RuntimeService, repo_root: Path, checkpoint_id: uuid.UUID):
    checkpoint = await db.get(AgentCheckpoint, checkpoint_id)
    agent = await db.get(Agent, checkpoint.agent_id)
    task = await db.get(Task, checkpoint.task_id)
    old_session = await db.get(AgentSession, checkpoint.agent_session_id)
    task_worktree = await find_task_worktree(db, checkpoint.task_id)
    allowed_servers = await resolve_agent_mcp_servers(db, repo_root, agent)
    return await rotate_session(db, runtime_service, repo_root, agent, task, task_worktree, old_session, checkpoint, allowed_servers)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-id", required=True)
    parser.add_argument("--repo-root", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main())
