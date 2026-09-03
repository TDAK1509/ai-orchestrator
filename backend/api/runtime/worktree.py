import asyncio
from pathlib import Path


class GitCommandError(RuntimeError):
    def __init__(self, args: list[str], returncode: int, stderr: str):
        super().__init__(f"git {' '.join(args)} failed ({returncode}): {stderr.strip()}")
        self.args_run = args
        self.returncode = returncode
        self.stderr = stderr


async def create_worktree(repo_root: Path, branch: str, path: Path, base_branch: str) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    await run_git(
        ["worktree", "add", "-b", branch, str(path), base_branch],
        cwd=repo_root,
    )


async def remove_worktree(repo_root: Path, path: Path) -> None:
    await run_git(["worktree", "remove", "--force", str(path)], cwd=repo_root)


async def push_worktree(path: Path, branch: str, remote: str = "origin") -> None:
    await run_git(["push", "-u", remote, branch], cwd=path)


async def commit_worktree(path: Path, message: str) -> str | None:
    await run_git(["add", "-A"], cwd=path)
    if not await has_staged_changes(path):
        return None
    await run_git(["commit", "-m", message], cwd=path)
    return await read_head_commit(path)


async def read_head_commit(path: Path) -> str:
    output = await run_git(["rev-parse", "HEAD"], cwd=path)
    return output.strip()


async def has_staged_changes(path: Path) -> bool:
    output = await run_git(["status", "--porcelain"], cwd=path)
    return bool(output.strip())


async def run_git(args: list[str], cwd: Path) -> str:
    process = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise GitCommandError(args, process.returncode, stderr.decode())
    return stdout.decode()
