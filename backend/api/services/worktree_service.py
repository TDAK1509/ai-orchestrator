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
    """PR 1: base_branch is the repository's stored ref (e.g. "origin/main") -- resolve_worktree_base fetches it fresh and returns the actual ref to cut from, falling back to a local branch when there's no matching remote."""
    branch = f"agent-office/{task.id}"
    # allow-comment: sibling of repo_root, not inside it, so it never shows up as untracked clutter in repo_root's own git status.
    path = repo_root.parent / ".agent-office" / "worktrees" / str(task.id)
    cut_from = await worktree_ops.resolve_worktree_base(repo_root, base_branch)
    await worktree_ops.create_worktree(repo_root, branch, path, cut_from)
    record = TaskWorktree(id=uuid.uuid4(), task_id=task.id, branch=branch, base_branch=base_branch, path=str(path))
    db.add(record)
    await commit(db)
    return record


async def remove_task_worktree(db: AsyncSession, task: Task) -> TaskWorktree | None:
    """Archiving a task (PR 0b): the git checkout goes, but the row stays REMOVED, not deleted -- task_worktrees.task_id must survive alongside the task it archives with."""
    task_worktree = await find_task_worktree(db, task.id)
    if task_worktree is None:
        return None
    repository = await resolve_task_repository(db, task)
    await worktree_ops.remove_worktree(resolve_repo_root(repository), Path(task_worktree.path))
    task_worktree.status = WorktreeStatus.REMOVED
    await commit(db)
    return task_worktree


async def resolve_task_repository(db: AsyncSession, task: Task) -> Repository:
    """A2/PR 4: repository_id is required, so this always resolves -- there is no workspace-default fallback left to fall back to."""
    return await db.get(Repository, task.repository_id)


def resolve_repo_root(repository: Repository) -> Path:
    return Path(repository.path)


def resolve_base_branch(repository: Repository) -> str:
    return repository.default_target_branch
