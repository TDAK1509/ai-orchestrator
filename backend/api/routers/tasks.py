import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import get_db, get_policy, get_repo_root, get_runtime_service
from events.bus import bus
from events.schema import TASK_ASSIGNED, TASK_CREATED, TASK_UPDATED
from lookups import get_or_404
from models.agent import Agent
from models.repository import Repository
from models.task import Task, TaskPriority
from serialization import serialize
from services.task_service import (
    archive_task,
    assign_task,
    create_task,
    edit_task,
    list_tasks,
    retry_task,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


class CreateTaskBody(BaseModel):
    title: str
    description: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    repository_id: uuid.UUID
    created_by_agent_id: uuid.UUID | None = None


class EditTaskBody(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: TaskPriority | None = None
    repository_id: uuid.UUID | None = None


class AssignTaskBody(BaseModel):
    agent_id: uuid.UUID


@router.get("")
async def list_tasks_route(db=Depends(get_db)):
    return [serialize(task) for task in await list_tasks(db)]


@router.post("", status_code=201)
async def create_task_route(body: CreateTaskBody, db=Depends(get_db)):
    await get_or_404(db, Repository, body.repository_id, "repository")
    if body.created_by_agent_id is not None:
        await get_or_404(db, Agent, body.created_by_agent_id, "agent")
    task = await create_task(db, body.title, body.description, body.priority, body.repository_id, body.created_by_agent_id)
    bus.publish(TASK_CREATED, serialize(task))
    return serialize(task)


@router.get("/{task_id}")
async def get_task_route(task_id: uuid.UUID, db=Depends(get_db)):
    task = await get_or_404(db, Task, task_id, "task")
    return serialize(task)


@router.patch("/{task_id}")
async def edit_task_route(task_id: uuid.UUID, body: EditTaskBody, db=Depends(get_db)):
    task = await get_or_404(db, Task, task_id, "task")
    if "repository_id" in body.model_fields_set and body.repository_id is not None:
        await get_or_404(db, Repository, body.repository_id, "repository")
    task = await edit_task(db, task, body, body.model_fields_set)
    bus.publish(TASK_UPDATED, serialize(task))
    return serialize(task)


@router.post("/{task_id}/archive")
async def archive_task_route(task_id: uuid.UUID, db=Depends(get_db), runtime_service=Depends(get_runtime_service)):
    task = await get_or_404(db, Task, task_id, "task")
    task = await archive_task(db, runtime_service, task)
    return serialize(task)


@router.post("/{task_id}/retry")
async def retry_task_route(task_id: uuid.UUID, db=Depends(get_db), runtime_service=Depends(get_runtime_service), repo_root=Depends(get_repo_root), policy=Depends(get_policy)):
    task = await get_or_404(db, Task, task_id, "task")
    task = await retry_task(db, runtime_service, repo_root, task, policy)
    return serialize(task)


@router.post("/{task_id}/assign")
async def assign_task_route(task_id: uuid.UUID, body: AssignTaskBody, db=Depends(get_db), runtime_service=Depends(get_runtime_service), repo_root=Depends(get_repo_root), policy=Depends(get_policy)):
    task, agent = await load_assignment_targets(db, task_id, body.agent_id)
    task = await assign_task(db, runtime_service, repo_root, task, agent, policy)
    bus.publish(TASK_ASSIGNED, serialize(task))
    return serialize(task)


async def load_assignment_targets(db, task_id: uuid.UUID, agent_id: uuid.UUID):
    task = await get_or_404(db, Task, task_id, "task")
    agent = await get_or_404(db, Agent, agent_id, "agent")
    return task, agent
