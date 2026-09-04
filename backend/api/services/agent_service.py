import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import commit
from events.bus import bus
from events.schema import TASK_UPDATED
from models.agent import Agent, AgentStatus
from models.session import AgentSession, ExecutionRun, RunStatus
from models.task import Task, TaskStatus
from runtime.runtime_service import RuntimeService
from serialization import serialize
from services.memory_service import archive_memory, list_agent_memories
from services.room_service import ensure_main_room


async def hire_agent(db: AsyncSession, name: str, role: str, instructions: str = "", team_id: uuid.UUID | None = None) -> Agent:
    """Rule 1 (README 23): there is always a Main Room, and every agent starts there."""
    main_room = await ensure_main_room(db)
    agent = Agent(id=uuid.uuid4(), name=name, role=role, instructions=instructions, room_id=main_room.id, team_id=team_id)
    db.add(agent)
    await commit(db)
    return agent


async def edit_agent(
    db: AsyncSession, agent: Agent, name: str | None = None, role: str | None = None, instructions: str | None = None
) -> Agent:
    apply_agent_edits(agent, name, role, instructions)
    await commit(db)
    return agent


def apply_agent_edits(agent: Agent, name: str | None, role: str | None, instructions: str | None) -> None:
    if name is not None:
        agent.name = name
    if role is not None:
        agent.role = role
    if instructions is not None:
        agent.instructions = instructions


async def fire_agent(db: AsyncSession, runtime_service: RuntimeService, agent: Agent) -> Agent:
    """Archives, never deletes: the task's worktree/branch/history, and the agent's own private memory (README 17.2), outlive the firing."""
    await stop_active_runtime(db, runtime_service, agent)
    released_task = await release_unfinished_task(db, agent)
    await archive_private_memory(db, agent)
    agent.active = False
    agent.status = AgentStatus.IDLE
    agent.room_id = None
    await commit(db)
    if released_task is not None:
        bus.publish(TASK_UPDATED, serialize(released_task))
    return agent


async def archive_private_memory(db: AsyncSession, agent: Agent) -> None:
    for record in await list_agent_memories(db, agent.id):
        await archive_memory(db, record)


async def stop_active_runtime(db: AsyncSession, runtime_service: RuntimeService, agent: Agent) -> None:
    run = await find_running_run_for_agent(db, agent)
    if run is not None:
        await runtime_service.kill_run(run.id)


async def find_running_run_for_agent(db: AsyncSession, agent: Agent) -> ExecutionRun | None:
    query = (
        select(ExecutionRun)
        .join(AgentSession, ExecutionRun.agent_session_id == AgentSession.id)
        .where(AgentSession.agent_id == agent.id, ExecutionRun.status == RunStatus.RUNNING)
    )
    result = await db.execute(query)
    return result.scalars().first()


async def release_unfinished_task(db: AsyncSession, agent: Agent) -> Task | None:
    if agent.current_task_id is None:
        return None
    task = await db.get(Task, agent.current_task_id)
    released = task is not None and task.status != TaskStatus.DONE
    if released:
        task.status = TaskStatus.BACKLOG
        task.assignee_id = None
    agent.current_task_id = None
    return task if released else None


async def restore_agent(db: AsyncSession, agent: Agent) -> Agent:
    main_room = await ensure_main_room(db)
    agent.active = True
    agent.room_id = main_room.id
    await commit(db)
    return agent


async def list_agents(db: AsyncSession, include_inactive: bool = False) -> list[Agent]:
    query = select(Agent)
    if not include_inactive:
        query = query.where(Agent.active.is_(True))
    return list((await db.execute(query.order_by(Agent.created_at))).scalars())
