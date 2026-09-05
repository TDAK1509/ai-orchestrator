import asyncio
from pathlib import Path

from .process import build_subprocess_env

NO_HOOKS_ARGS = ["-c", "core.hooksPath=/dev/null"]
SCRATCH_IGNORE_LINE = ".scratch/"


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
    await ensure_scratch_ignored(path)


async def ensure_scratch_ignored(path: Path) -> None:
    """Gives agents somewhere to put scratch work that never lands in a commit (PR 2): `info/exclude` lives in the repo's shared git-common-dir, so this one write covers every worktree, not just this one."""
    exclude_file = await resolve_exclude_file(path)
    append_scratch_ignore_line(exclude_file)


async def resolve_exclude_file(path: Path) -> Path:
    common_dir = await run_git(["rev-parse", "--git-common-dir"], cwd=path)
    return (path / common_dir.strip()).resolve() / "info" / "exclude"


def append_scratch_ignore_line(exclude_file: Path) -> None:
    if exclude_file.exists() and SCRATCH_IGNORE_LINE in exclude_file.read_text().splitlines():
        return
    exclude_file.parent.mkdir(parents=True, exist_ok=True)
    with exclude_file.open("a") as handle:
        handle.write(f"{SCRATCH_IGNORE_LINE}\n")


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


async def commit_paths(path: Path, relative_paths: list[str], message: str) -> str | None:
    """Never `add -A`: the caller is committing on our own behalf (README 19.3), not staging agent-written files it hasn't chosen."""
    for relative_path in relative_paths:
        await run_git(["add", relative_path], cwd=path)
    return await commit_if_staged(path, message)


async def resolve_paths_to_commit(path: Path) -> list[str]:
    """Tracked modifications plus untracked-and-not-ignored files (PR 2): what `git add -A` would stage minus whatever `.gitignore` -- including the worktree's `.scratch/` -- excludes."""
    return await list_modified_paths(path) + await list_untracked_paths(path)


async def list_modified_paths(path: Path) -> list[str]:
    output = await run_git(["diff", "--name-only", "HEAD"], cwd=path)
    return [line for line in output.splitlines() if line]


async def list_untracked_paths(path: Path) -> list[str]:
    output = await run_git(["ls-files", "--others", "--exclude-standard"], cwd=path)
    return [line for line in output.splitlines() if line]


async def commit_if_staged(path: Path, message: str) -> str | None:
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
