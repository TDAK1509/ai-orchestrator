import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.agent import Agent, AgentStatus
from models.attention import AttentionEvent, AttentionType
from models.base import utcnow
from models.decision import DecisionRequest, DecisionStatus
from models.task import Task, TaskStatus


async def create_decision_request(db: AsyncSession, agent: Agent, task: Task | None, question: str, options: list[dict] | None = None, allow_custom_answer: bool = True) -> DecisionRequest:
    """The blocking half of README 19.7's ask_human tool: the caller awaits until answer_decision resolves this row."""
    decision = build_decision_request(agent, task, question, options, allow_custom_answer)
    db.add(decision)
    block_agent_and_task(agent, task)
    db.add(build_decision_attention_event(agent, task, decision, question))
    await db.commit()
    return decision


def build_decision_request(
    agent: Agent, task: Task | None, question: str, options: list[dict] | None, allow_custom_answer: bool
) -> DecisionRequest:
    return DecisionRequest(
        id=uuid.uuid4(),
        agent_id=agent.id,
        task_id=task.id if task else None,
        question=question,
        options=options,
        allow_custom_answer=allow_custom_answer,
    )


def block_agent_and_task(agent: Agent, task: Task | None) -> None:
    agent.status = AgentStatus.BLOCKED
    agent.needs_attention = True
    if task is not None:
        task.status = TaskStatus.BLOCKED


def build_decision_attention_event(agent: Agent, task: Task | None, decision: DecisionRequest, question: str) -> AttentionEvent:
    return AttentionEvent(
        id=uuid.uuid4(),
        type=AttentionType.DECISION_REQUIRED,
        agent_id=agent.id,
        task_id=task.id if task else None,
        decision_request_id=decision.id,
        title=f"{agent.name} needs a decision",
        message=question,
    )


async def answer_decision(db: AsyncSession, decision_id: uuid.UUID, answer: str) -> DecisionRequest:
    """The other half of the round trip (README 31.3): unblocks agent and task, and lets the waiting tool call return."""
    decision = await db.get(DecisionRequest, decision_id)
    decision.status = DecisionStatus.ANSWERED
    decision.answer = answer
    decision.answered_at = utcnow()
    await resolve_attention_event(db, decision)
    await unblock_agent_and_task(db, decision)
    await db.commit()
    return decision


async def resolve_attention_event(db: AsyncSession, decision: DecisionRequest) -> None:
    query = select(AttentionEvent).where(AttentionEvent.decision_request_id == decision.id)
    event = (await db.execute(query)).scalars().first()
    if event is not None:
        event.resolved = True
        event.resolved_at = utcnow()


async def unblock_agent_and_task(db: AsyncSession, decision: DecisionRequest) -> None:
    agent = await db.get(Agent, decision.agent_id)
    agent.status = AgentStatus.WORKING
    agent.needs_attention = await has_pending_decision(db, agent.id)
    if decision.task_id is not None:
        task = await db.get(Task, decision.task_id)
        task.status = TaskStatus.IN_PROGRESS


async def has_pending_decision(db: AsyncSession, agent_id: uuid.UUID) -> bool:
    query = select(func.count()).select_from(DecisionRequest).where(
        DecisionRequest.agent_id == agent_id, DecisionRequest.status == DecisionStatus.PENDING
    )
    result = await db.execute(query)
    return result.scalar_one() > 0
