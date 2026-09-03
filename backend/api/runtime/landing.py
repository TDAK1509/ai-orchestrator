from pathlib import Path

from .worktree import (
    GitCommandError,
    has_staged_changes,
    read_current_branch,
    read_head_commit,
    run_git,
    run_subprocess,
)


class DirectMergeUnsafeError(RuntimeError):
    pass


async def merge_direct(repo_root: Path, branch: str, target_branch: str) -> str:
    """Only ever merges into a clean, already-checked-out target: never checks target_branch out itself, since repo_root may be the developer's own working tree."""
    await require_clean_checkout_of(repo_root, target_branch)
    await attempt_merge(repo_root, branch)
    return await read_head_commit(repo_root)


async def attempt_merge(repo_root: Path, branch: str) -> None:
    try:
        await run_git(["merge", "--no-ff", "--no-edit", branch], cwd=repo_root)
    except GitCommandError:
        await run_git(["merge", "--abort"], cwd=repo_root)
        raise


async def require_clean_checkout_of(repo_root: Path, target_branch: str) -> None:
    current_branch = await read_current_branch(repo_root)
    if current_branch != target_branch:
        raise DirectMergeUnsafeError(f"{repo_root} is on {current_branch!r}, expected {target_branch!r}")
    if await has_staged_changes(repo_root):
        raise DirectMergeUnsafeError(f"{repo_root} has uncommitted changes; refusing to merge onto it")


async def open_pull_request(path: Path, base_branch: str, head_branch: str, title: str, body: str) -> tuple[int, str]:
    args = ["pr", "create", "--base", base_branch, "--head", head_branch, "--title", title, "--body", body]
    output = await run_gh(args, cwd=path)
    url = output.strip().splitlines()[-1].strip()
    return int(url.rstrip("/").rsplit("/", 1)[-1]), url


async def run_gh(args: list[str], cwd: Path) -> str:
    argv = ["gh", *args]
    stdout, stderr, returncode = await run_subprocess(argv, cwd)
    if returncode != 0:
        raise GitCommandError(argv, returncode, stderr.decode())
    return stdout.decode()
