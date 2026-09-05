import asyncio
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
    target = resolve_existing_directory(path)
    # allow-comment: codex P2 -- iterdir()/is_dir()/.git existence are all blocking syscalls; off the event loop so one slow or huge (e.g. network-mounted) directory can't stall every other request.
    entries = await asyncio.to_thread(list_subdirectories, target)
    return DirectoryListing(entries=entries)


def resolve_existing_directory(path: str | None) -> Path:
    target = Path(path) if path else Path.home()
    if not target.is_absolute() or not target.is_dir():
        raise HTTPException(status_code=404, detail="directory not found")
    return target


def list_subdirectories(target: Path) -> list[DirectoryEntry]:
    entries = [build_entry(child) for child in safely_list(target) if is_readable_directory(child)]
    return sorted(entries, key=lambda entry: entry.name)


def safely_list(target: Path) -> list[Path]:
    try:
        return list(target.iterdir())
    except OSError:
        return []


def is_readable_directory(child: Path) -> bool:
    try:
        return child.is_dir()
    except OSError:
        return False


def build_entry(child: Path) -> DirectoryEntry:
    return DirectoryEntry(name=child.name, path=str(child), is_directory=True, is_git_repo=is_git_repo(child))


def is_git_repo(directory: Path) -> bool:
    try:
        return (directory / ".git").exists()
    except OSError:
        return False
