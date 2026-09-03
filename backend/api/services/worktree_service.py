import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import commit
from models.task import Task
from models.worktree import TaskWorktree
from runtime import worktree as worktree_ops


async def ensure_task_worktree(
    db: AsyncSession, repo_root: Path, task: Task, base_branch: str = "main"
) -> TaskWorktree:
    """One worktree per task (README 19.3): reuse the existing row rather than creating a second one."""
    existing = await find_task_worktree(db, task.id)
    if existing is not None:
        return existing
    return await create_task_worktree(db, repo_root, task, base_branch)


async def find_task_worktree(db: AsyncSession, task_id: uuid.UUID) -> TaskWorktree | None:
    result = await db.execute(select(TaskWorktree).where(TaskWorktree.task_id == task_id))
    return result.scalars().first()


async def create_task_worktree(db: AsyncSession, repo_root: Path, task: Task, base_branch: str) -> TaskWorktree:
    branch = f"agent-office/{task.id}"
    # allow-comment: sibling of repo_root, not inside it, so it never shows up as untracked clutter in repo_root's own git status.
    path = repo_root.parent / ".agent-office" / "worktrees" / str(task.id)
    await worktree_ops.create_worktree(repo_root, branch, path, base_branch)
    record = TaskWorktree(id=uuid.uuid4(), task_id=task.id, branch=branch, base_branch=base_branch, path=str(path))
    db.add(record)
    await commit(db)
    return record
