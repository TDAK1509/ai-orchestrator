#!/usr/bin/env python3
"""Proves RuntimeService end to end from the command line, before any UI exists.

Drives tests/fixtures/fake_claude.py by default, or pass --claude-binary claude for the real CLI.
"""
import argparse
import asyncio
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models.agent import Agent
from models.base import Base, utcnow
from models.session import AgentSession, BoundVia, ExecutionRun, RunStatus
from models.task import Task
from models.worktree import TaskWorktree
from runtime import worktree as worktree_ops
from runtime.prompt import build_initial_user_message
from runtime.runtime_service import RuntimeService, RuntimeSettings

DEFAULT_FAKE_CLAUDE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "fake_claude.py"


async def main() -> None:
    args = parse_args()
    workspace = Path(tempfile.mkdtemp(prefix="agent-office-proof-"))
    try:
        await run_proof(workspace, args.claude_binary)
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude-binary", default=str(DEFAULT_FAKE_CLAUDE))
    return parser.parse_args()


async def run_proof(workspace: Path, claude_binary: str) -> None:
    session_factory = await build_session_factory()
    async with session_factory() as db:
        service = RuntimeService(db, RuntimeSettings(claude_binary=claude_binary, runtime_root=workspace / "runtime"))
        repo_root = await seed_repo(workspace)
        agent, task, task_worktree = await seed_domain_rows(db, repo_root, workspace)

        run = await spawn_and_stream(service, agent, task, task_worktree)
        await resume_and_stream(service, agent, task_worktree, run)
        await prove_kill(service, agent, task_worktree)
        await prove_reconcile(service, db, agent, task_worktree)


async def build_session_factory():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


async def seed_repo(workspace: Path) -> Path:
    repo_root = workspace / "repo"
    await worktree_ops.run_git(["init", "-b", "main", str(repo_root)], cwd=workspace)
    await worktree_ops.run_git(["config", "user.email", "proof@example.com"], cwd=repo_root)
    await worktree_ops.run_git(["config", "user.name", "Proof"], cwd=repo_root)
    (repo_root / "README.md").write_text("seed\n")
    await worktree_ops.run_git(["add", "-A"], cwd=repo_root)
    await worktree_ops.run_git(["commit", "-m", "seed"], cwd=repo_root)
    return repo_root


async def seed_domain_rows(db, repo_root: Path, workspace: Path) -> tuple[Agent, Task, TaskWorktree]:
    agent = Agent(id=uuid.uuid4(), name="Alex", role="Backend Engineer", instructions="")
    task = Task(id=uuid.uuid4(), title="Fix refresh-token rotation")
    db.add_all([agent, task])
    path = workspace / "worktrees" / str(task.id)
    branch = f"agent-office/{task.id}"
    await worktree_ops.create_worktree(repo_root, branch, path, "main")
    task_worktree = TaskWorktree(id=uuid.uuid4(), task_id=task.id, branch=branch, base_branch="main", path=str(path))
    db.add(task_worktree)
    await db.flush()
    return agent, task, task_worktree


async def spawn_and_stream(service: RuntimeService, agent: Agent, task: Task, task_worktree: TaskWorktree):
    print("--- spawn ---")
    run = await service.spawn(agent, task_worktree, [], build_initial_user_message(task))
    async for event in service.stream_events(run.id):
        print(f"  event: {event.kind} {event.text or event.tool_name or event.claude_session_id or ''}")
    print(f"  run status={run.status.value} before={run.before_head_commit[:7]} after={run.after_head_commit[:7]}")
    return run


async def resume_and_stream(service: RuntimeService, agent: Agent, task_worktree: TaskWorktree, run) -> None:
    print("--- resume ---")
    agent_session = await service.db.get(AgentSession, run.agent_session_id)
    resumed = await service.resume(agent, agent_session, task_worktree, [], "please continue")
    async for event in service.stream_events(resumed.id):
        print(f"  event: {event.kind}")
    print(f"  resumed run bound_via={resumed.bound_via.value} status={resumed.status.value}")


async def prove_kill(service: RuntimeService, agent: Agent, task_worktree: TaskWorktree) -> None:
    print("--- kill a hung run ---")
    os.environ["FAKE_CLAUDE_HANG"] = "1"
    run = await service.spawn(agent, task_worktree, [], {"type": "user", "message": {"role": "user", "content": "hang"}})
    consumer = asyncio.create_task(drain(service.stream_events(run.id)))
    await asyncio.sleep(0.3)
    await service.kill_run(run.id)
    await asyncio.wait_for(consumer, timeout=5)
    os.environ.pop("FAKE_CLAUDE_HANG", None)
    print(f"  run status={run.status.value}")


async def drain(events) -> None:
    async for _ in events:
        pass


async def prove_reconcile(service: RuntimeService, db, agent: Agent, task_worktree: TaskWorktree) -> None:
    print("--- reconcile orphans on startup ---")
    await seed_orphan_run(db, agent, task_worktree)
    reconciled = await service.reconcile_orphans()
    print(f"  reconciled {len(reconciled)} orphan run(s) -> status={reconciled[0].status.value}")


async def seed_orphan_run(db, agent: Agent, task_worktree: TaskWorktree) -> None:
    orphan_session = AgentSession(id=uuid.uuid4(), agent_id=agent.id, task_worktree_id=task_worktree.id, cwd=task_worktree.path)
    orphan_run = ExecutionRun(
        id=uuid.uuid4(),
        agent_session_id=orphan_session.id,
        bound_via=BoundVia.SPAWN,
        status=RunStatus.RUNNING,
        pid=999999999,
        started_at=utcnow(),
    )
    db.add_all([orphan_session, orphan_run])
    await db.flush()


if __name__ == "__main__":
    asyncio.run(main())
