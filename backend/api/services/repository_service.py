import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import commit
from models.repository import Repository
from runtime.worktree import GitCommandError, run_git


async def list_repositories(db: AsyncSession) -> list[Repository]:
    result = await db.execute(select(Repository).order_by(Repository.created_at))
    return list(result.scalars())


async def create_repository(db: AsyncSession, path: str, name: str | None, default_target_branch: str) -> Repository:
    resolved_path = await verify_git_repository(path)
    repository = Repository(
        id=uuid.uuid4(), name=name or resolved_path.name, path=str(resolved_path),
        default_target_branch=default_target_branch,
    )
    db.add(repository)
    await commit(db)
    return repository


async def verify_git_repository(path: str) -> Path:
    """A1: reject a typo at creation, not at the first spawn -- `.git` existing (A0's cheap picker probe) is not proof git itself can use the directory."""
    resolved = require_absolute_existing_directory(path)
    try:
        await run_git(["rev-parse", "--git-dir"], cwd=resolved)
    except GitCommandError as error:
        raise ValueError(f"{resolved} is not a git repository") from error
    return resolved


def require_absolute_existing_directory(path: str) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute() or not resolved.is_dir():
        raise ValueError(f"{path} is not an existing absolute directory")
    return resolved
