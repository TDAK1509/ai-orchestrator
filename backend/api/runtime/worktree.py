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


async def resolve_worktree_base(repo_root: Path, target_ref: str) -> str:
    """PR 1: fetches the remote branch behind a ref like "origin/main" right before cutting from it, instead of whatever a stale local ref last pulled -- but only once has_remote confirms the first segment really names one, so a local branch whose own name contains a slash (e.g. "release/1.0") is never mistaken for a remote-qualified ref."""
    remote, branch = split_remote_ref(target_ref)
    if remote is not None and await has_remote(repo_root, remote):
        await fetch_remote_branch(repo_root, remote, branch)
    return target_ref


async def local_branch_name_for(repo_root: Path, ref: str) -> str:
    """The plain branch name landing merges into or opens a PR against -- "origin/main" strips to "main" only when `origin` genuinely exists; a local branch like "release/1.0" is returned whole, not truncated at its first slash."""
    remote, branch = split_remote_ref(ref)
    if remote is not None and await has_remote(repo_root, remote):
        return branch
    return ref


async def has_remote(repo_root: Path, remote: str) -> bool:
    return await remote_url(repo_root, remote) is not None


async def has_github_remote(repo_root: Path, remote: str) -> bool:
    """PR 2: `gh pr create` only works against a GitHub remote -- landing via PR needs more than "a remote exists", it needs specifically this one to be GitHub's."""
    url = await remote_url(repo_root, remote)
    return url is not None and "github.com" in url


async def remote_url(repo_root: Path, remote: str) -> str | None:
    try:
        return (await run_git(["remote", "get-url", remote], cwd=repo_root)).strip()
    except GitCommandError:
        return None


async def fetch_remote_branch(repo_root: Path, remote: str, branch: str) -> None:
    await run_git(["fetch", remote, branch], cwd=repo_root)


def split_remote_ref(ref: str) -> tuple[str | None, str]:
    """"origin/main" -> ("origin", "main"); "main" -> (None, "main"). This is only ever a candidate parse -- the caller must still confirm the first segment names a real remote before treating it as one."""
    remote, separator, branch = ref.partition("/")
    return (remote, branch) if separator else (None, ref)


async def create_worktree(repo_root: Path, branch: str, path: Path, base_branch: str) -> None:
    if path.exists():
        await verify_existing_worktree(path, branch)
    else:
        await create_new_worktree(repo_root, branch, path, base_branch)
    await ensure_scratch_ignored(path)


async def create_new_worktree(repo_root: Path, branch: str, path: Path, base_branch: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    await run_git(
        ["worktree", "add", "-b", branch, str(path), base_branch],
        cwd=repo_root,
    )


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
    """Never `add -A`: the caller is committing on our own behalf (README 19.3), not staging agent-written files it hasn't chosen. One `git add` call behind `--`, not one per path: a filename starting with `-` can't be read as an option, and staging is O(1) subprocesses instead of O(paths)."""
    if relative_paths:
        await run_git(["add", "--", *relative_paths], cwd=path)
    return await commit_if_staged(path, message)


async def resolve_paths_to_commit(path: Path) -> list[str]:
    """Tracked modifications plus untracked-and-not-ignored files (PR 2): what `git add -A` would stage minus whatever `.gitignore` -- including the worktree's `.scratch/` -- excludes."""
    return await list_modified_paths(path) + await list_untracked_paths(path)


async def list_modified_paths(path: Path) -> list[str]:
    output = await run_git(["diff", "--name-only", "-z", "HEAD"], cwd=path)
    return split_nul_delimited(output)


async def list_untracked_paths(path: Path) -> list[str]:
    output = await run_git(["ls-files", "--others", "--exclude-standard", "-z"], cwd=path)
    return split_nul_delimited(output)


def split_nul_delimited(output: str) -> list[str]:
    """`-z`-terminated git output, not newline-split: a path containing a literal newline stays one entry instead of splitting into two."""
    return [entry for entry in output.split("\0") if entry]


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
