import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import get_db, get_policy, get_repo_root, get_runtime_service
from events.bus import bus
from events.schema import TASK_ASSIGNED, TASK_CREATED
from lookups import get_or_404
from models.agent import Agent
from models.task import Task, TaskPriority
from serialization import serialize
from services.task_service import assign_task, create_task, list_tasks

router = APIRouter(prefix="/tasks", tags=["tasks"])


class CreateTaskBody(BaseModel):
    title: str
    description: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM


class AssignTaskBody(BaseModel):
    agent_id: uuid.UUID


@router.get("")
async def list_tasks_route(db=Depends(get_db)):
    return [serialize(task) for task in await list_tasks(db)]


@router.post("", status_code=201)
async def create_task_route(body: CreateTaskBody, db=Depends(get_db)):
    task = await create_task(db, body.title, body.description, body.priority)
    bus.publish(TASK_CREATED, serialize(task))
    return serialize(task)


@router.get("/{task_id}")
async def get_task_route(task_id: uuid.UUID, db=Depends(get_db)):
    task = await get_or_404(db, Task, task_id, "task")
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
