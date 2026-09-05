import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import commit
from models.repository import Repository
from runtime.worktree import (
    GitCommandError,
    has_github_remote,
    has_remote,
    read_current_branch,
    run_git,
)

REMOTE_HEAD_REF_PREFIX = "refs/remotes/origin/"


async def list_repositories(db: AsyncSession) -> list[Repository]:
    result = await db.execute(select(Repository).order_by(Repository.created_at))
    return list(result.scalars())


async def inspect_repository(path: str) -> dict:
    """PR 3: what the registration dialog needs before the user commits. The branch to prefill follows any remote at all -- fetch-freshness benefits a GitLab or Bitbucket repository just as much as a GitHub one -- but the `has_remote` reported here is GitHub-specifically, since that's the one thing that actually decides PR-versus-direct landing (`gh pr create` works nowhere else)."""
    toplevel = await verify_git_repository(path)
    remote_exists = await has_remote(toplevel, "origin")
    pr_capable = remote_exists and await has_github_remote(toplevel, "origin")
    default_target_branch = await resolve_default_target_branch(toplevel, remote_exists)
    return {"path": str(toplevel), "has_remote": pr_capable, "default_target_branch": default_target_branch}


async def resolve_default_target_branch(toplevel: Path, remote_exists: bool) -> str:
    if not remote_exists:
        return await read_current_branch(toplevel)
    branch = await resolve_remote_head_branch(toplevel)
    return f"origin/{branch}" if branch else "origin/main"


async def resolve_remote_head_branch(toplevel: Path) -> str | None:
    """Strips the known `refs/remotes/origin/` prefix, not just the last path segment -- the remote's default branch can itself contain a slash (e.g. "release/1.0")."""
    try:
        output = await run_git(["symbolic-ref", "refs/remotes/origin/HEAD"], cwd=toplevel)
    except GitCommandError:
        return None
    ref = output.strip()
    return ref[len(REMOTE_HEAD_REF_PREFIX):] if ref.startswith(REMOTE_HEAD_REF_PREFIX) else None


async def create_repository(db: AsyncSession, path: str, name: str | None, default_target_branch: str) -> Repository:
    resolved_path = await verify_git_repository(path)
    await verify_branch_exists(resolved_path, default_target_branch)
    repository = Repository(
        id=uuid.uuid4(), name=name or resolved_path.name, path=str(resolved_path),
        default_target_branch=default_target_branch,
    )
    db.add(repository)
    await commit(db)
    return repository


async def verify_git_repository(path: str) -> Path:
    """A1: reject a typo at creation, not at the first spawn -- `.git` existing (A0's cheap picker probe) is not proof git itself can use the directory as a worktree source."""
    candidate = require_absolute_existing_directory(path)
    toplevel = await resolve_toplevel(candidate)
    await reject_bare_repository(toplevel)
    return toplevel


def require_absolute_existing_directory(path: str) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute() or not resolved.is_dir():
        raise ValueError(f"{path} is not an existing absolute directory")
    return resolved


async def resolve_toplevel(candidate: Path) -> Path:
    """codex P2: `--git-dir` succeeds from any subdirectory of a checkout, not just its root -- registering a subdirectory would cut worktrees at the wrong ancestor and dirty an unrelated tree."""
    try:
        output = await run_git(["rev-parse", "--show-toplevel"], cwd=candidate)
    except GitCommandError as error:
        raise ValueError(f"{candidate} is not a git repository") from error
    return Path(output.strip())


async def reject_bare_repository(toplevel: Path) -> None:
    output = await run_git(["rev-parse", "--is-bare-repository"], cwd=toplevel)
    if output.strip() == "true":
        raise ValueError(f"{toplevel} is a bare repository, not a checkout a worktree can be cut from")


async def verify_branch_exists(repo_path: Path, branch: str) -> None:
    """codex P1: an unresolvable default_target_branch would otherwise only fail once a task tries to spawn a worktree from it -- by then the task and agent are already committed to IN_PROGRESS/WORKING with no undo."""
    try:
        await run_git(["rev-parse", "--verify", "--quiet", f"{branch}^{{commit}}"], cwd=repo_path)
    except GitCommandError as error:
        raise ValueError(f"{repo_path} has no branch or ref named {branch!r}") from error
