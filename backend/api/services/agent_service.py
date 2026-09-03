import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.agent import Agent, AgentStatus
from models.session import AgentSession, ExecutionRun, RunStatus
from models.task import Task, TaskStatus
from runtime.runtime_service import RuntimeService


async def hire_agent(db: AsyncSession, name: str, role: str, instructions: str = "") -> Agent:
    agent = Agent(id=uuid.uuid4(), name=name, role=role, instructions=instructions)
    db.add(agent)
    await db.commit()
    return agent


async def edit_agent(
    db: AsyncSession, agent: Agent, name: str | None = None, role: str | None = None, instructions: str | None = None
) -> Agent:
    apply_agent_edits(agent, name, role, instructions)
    await db.commit()
    return agent


def apply_agent_edits(agent: Agent, name: str | None, role: str | None, instructions: str | None) -> None:
    if name is not None:
        agent.name = name
    if role is not None:
        agent.role = role
    if instructions is not None:
        agent.instructions = instructions


async def fire_agent(runtime_service: RuntimeService, agent: Agent) -> Agent:
    """Archives, never deletes: the task's worktree/branch/history outlive the agent that started them."""
    await stop_active_runtime(runtime_service, agent)
    await release_unfinished_task(runtime_service.db, agent)
    agent.active = False
    agent.status = AgentStatus.IDLE
    await runtime_service.commit()
    return agent


async def stop_active_runtime(runtime_service: RuntimeService, agent: Agent) -> None:
    run = await find_running_run_for_agent(runtime_service.db, agent)
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


async def release_unfinished_task(db: AsyncSession, agent: Agent) -> None:
    if agent.current_task_id is None:
        return
    task = await db.get(Task, agent.current_task_id)
    if task is not None and task.status != TaskStatus.DONE:
        task.status = TaskStatus.BACKLOG
        task.assignee_id = None
    agent.current_task_id = None


async def restore_agent(db: AsyncSession, agent: Agent) -> Agent:
    agent.active = True
    await db.commit()
    return agent
