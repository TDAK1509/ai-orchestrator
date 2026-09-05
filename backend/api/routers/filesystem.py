import asyncio
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/filesystem", tags=["filesystem"])


class DirectoryEntry(BaseModel):
    name: str
    path: str
    is_directory: bool
    is_git_repo: bool


class DirectoryListing(BaseModel):
    entries: list[DirectoryEntry]


@router.get("/directory", response_model=DirectoryListing)
async def list_directory_route(path: str | None = None) -> DirectoryListing:
    """A0: a names-only filesystem oracle for the repository picker -- never reads file contents or sizes, only entry names and a cheap `.git` existence probe (README appendix: `.git` is a file inside a worktree, not just a directory, so is_dir() alone would mislabel one)."""
    require_absolute_path(path)
    # allow-comment: codex P2 -- resolve(), iterdir(), is_dir() and the .git probe are all blocking syscalls; off the event loop so one slow or huge (e.g. network-mounted) directory can't stall every other request.
    entries = await asyncio.to_thread(list_contained_subdirectories, path)
    return DirectoryListing(entries=entries)


def require_absolute_path(path: str | None) -> None:
    if path is not None and not Path(path).is_absolute():
        raise HTTPException(status_code=404, detail="directory not found")


def list_contained_subdirectories(path: str | None) -> list[DirectoryEntry]:
    root = read_browse_root()
    target = resolve_contained_directory(path, root)
    entries = [build_entry(child) for child in safely_list(target) if is_listable_child(child, root)]
    return sorted(entries, key=lambda entry: entry.name)


def read_browse_root() -> Path:
    """The picker can reach anywhere the backend user can read, and that is a wider boundary than it looks: AGENT_OFFICE_API_TOKEN is unset by default and the app is reached over an ssh -L tunnel, so binding to 127.0.0.1 is not the containment it reads as."""
    return Path(os.environ.get("AGENT_OFFICE_BROWSE_ROOT") or Path.home()).resolve()


def resolve_contained_directory(path: str | None, root: Path) -> Path:
    """404 rather than 403 for a path outside the root: a distinct status would confirm that the path exists."""
    target = Path(path).resolve() if path else root
    if not is_contained_directory(target, root):
        raise HTTPException(status_code=404, detail="directory not found")
    return target


def is_contained_directory(target: Path, root: Path) -> bool:
    """Resolved before comparing, so neither `..` nor a symlink can name a directory outside the root."""
    return target.is_dir() and target.is_relative_to(root)


def is_listable_child(child: Path, root: Path) -> bool:
    """A symlink under the root pointing outside it is hidden rather than shown: listing it would offer a path the picker itself would then 404 on."""
    try:
        return child.is_dir() and child.resolve().is_relative_to(root)
    except OSError:
        return False


def safely_list(target: Path) -> list[Path]:
    try:
        return list(target.iterdir())
    except OSError:
        return []


def build_entry(child: Path) -> DirectoryEntry:
    return DirectoryEntry(name=child.name, path=str(child), is_directory=True, is_git_repo=is_git_repo(child))


def is_git_repo(directory: Path) -> bool:
    try:
        return (directory / ".git").exists()
    except OSError:
        return False
