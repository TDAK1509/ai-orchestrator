from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import get_db
from serialization import serialize
from services.repository_service import create_repository, list_repositories

router = APIRouter(prefix="/repositories", tags=["repositories"])


class CreateRepositoryBody(BaseModel):
    path: str
    name: str | None = None
    default_target_branch: str = "main"


@router.get("")
async def list_repositories_route(db=Depends(get_db)):
    return [serialize(repository) for repository in await list_repositories(db)]


@router.post("", status_code=201)
async def create_repository_route(body: CreateRepositoryBody, db=Depends(get_db)):
    repository = await create_repository(db, body.path, body.name, body.default_target_branch)
    return serialize(repository)
