import asyncio
from pathlib import Path

from .process import build_subprocess_env

NO_HOOKS_ARGS = ["-c", "core.hooksPath=/dev/null"]


class GitCommandError(RuntimeError):
    def __init__(self, argv: list[str], returncode: int, stderr: str):
        super().__init__(f"{' '.join(argv)} failed ({returncode}): {stderr.strip()}")
        self.argv = argv
        self.returncode = returncode
        self.stderr = stderr


class WorktreeMismatchError(RuntimeError):
    def __init__(self, path: Path, expected_branch: str, actual_branch: str):
        super().__init__(f"{path} exists but is on branch {actual_branch!r}, expected {expected_branch!r}")


async def create_worktree(repo_root: Path, branch: str, path: Path, base_branch: str) -> None:
    if path.exists():
        await verify_existing_worktree(path, branch)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    await run_git(
        ["worktree", "add", "-b", branch, str(path), base_branch],
        cwd=repo_root,
    )


async def verify_existing_worktree(path: Path, branch: str) -> None:
    actual_branch = await read_current_branch(path)
    if actual_branch != branch:
        raise WorktreeMismatchError(path, branch, actual_branch)


async def read_current_branch(path: Path) -> str:
    output = await run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=path)
    return output.strip()


async def remove_worktree(repo_root: Path, path: Path) -> None:
    await run_git(["worktree", "remove", "--force", str(path)], cwd=repo_root)


async def push_worktree(path: Path, branch: str, remote: str = "origin") -> None:
    await run_git(["push", "-u", remote, branch], cwd=path)


async def commit_worktree(path: Path, message: str) -> str | None:
    await run_git(["add", "-A"], cwd=path)
    if not await has_staged_changes(path):
        return None
    await run_git(["commit", "--no-verify", "-m", message], cwd=path)
    return await read_head_commit(path)


async def read_head_commit(path: Path) -> str:
    output = await run_git(["rev-parse", "HEAD"], cwd=path)
    return output.strip()


async def has_staged_changes(path: Path) -> bool:
    output = await run_git(["status", "--porcelain"], cwd=path)
    return bool(output.strip())


async def run_git(args: list[str], cwd: Path) -> str:
    """Hooks disabled, secret-free environment: the task worktree's contents are agent-controlled, not trusted."""
    argv = ["git", *NO_HOOKS_ARGS, *args]
    stdout, stderr, returncode = await run_subprocess(argv, cwd)
    if returncode != 0:
        raise GitCommandError(argv, returncode, stderr.decode())
    return stdout.decode()


async def run_subprocess(argv: list[str], cwd: Path) -> tuple[bytes, bytes, int]:
    process = await asyncio.create_subprocess_exec(
        *argv, cwd=str(cwd), env=build_subprocess_env(), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return stdout, stderr, process.returncode
