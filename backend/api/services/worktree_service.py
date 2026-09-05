import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import commit
from models.repository import Repository
from models.task import Task
from models.worktree import TaskWorktree, WorktreeStatus
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


async def remove_task_worktree(db: AsyncSession, default_repo_root: Path, task: Task) -> TaskWorktree | None:
    """Archiving a task (PR 0b): the git checkout goes, but the row stays REMOVED, not deleted -- task_worktrees.task_id must survive alongside the task it archives with."""
    task_worktree = await find_task_worktree(db, task.id)
    if task_worktree is None:
        return None
    repository = await resolve_task_repository(db, task)
    repo_root = resolve_repo_root(repository, default_repo_root)
    await worktree_ops.remove_worktree(repo_root, Path(task_worktree.path))
    task_worktree.status = WorktreeStatus.REMOVED
    await commit(db)
    return task_worktree


async def resolve_task_repository(db: AsyncSession, task: Task) -> Repository | None:
    """A2: a task with no repository_id keeps using the workspace's injected default -- every task created before this column existed."""
    if task.repository_id is None:
        return None
    return await db.get(Repository, task.repository_id)


def resolve_repo_root(repository: Repository | None, default_repo_root: Path) -> Path:
    return Path(repository.path) if repository else default_repo_root


def resolve_base_branch(repository: Repository | None, default_base_branch: str) -> str:
    return repository.default_target_branch if repository else default_base_branch
