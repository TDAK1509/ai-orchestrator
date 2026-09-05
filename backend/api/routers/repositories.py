from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import get_db
from routers.filesystem import read_browse_root, resolve_contained_directory
from serialization import serialize
from services.repository_service import (
    create_repository,
    inspect_repository,
    list_repositories,
)

router = APIRouter(prefix="/repositories", tags=["repositories"])


class CreateRepositoryBody(BaseModel):
    path: str
    name: str | None = None
    default_target_branch: str = "origin/main"


@router.get("")
async def list_repositories_route(db=Depends(get_db)):
    return [serialize(repository) for repository in await list_repositories(db)]


@router.get("/inspect")
async def inspect_repository_route(path: str):
    """PR 3: registered ahead of a future GET /{repository_id} -- "inspect" must never be parsed as a repository id. Contained to the same browse root the directory picker is (filesystem.py), so this read-only probe can't be pointed at an arbitrary path elsewhere on disk."""
    resolve_contained_directory(path, read_browse_root())
    return await inspect_repository(path)


@router.post("", status_code=201)
async def create_repository_route(body: CreateRepositoryBody, db=Depends(get_db)):
    repository = await create_repository(db, body.path, body.name, body.default_target_branch)
    return serialize(repository)
