import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db import commit
from events.bus import bus
from events.schema import (
    AGENT_STATUS_CHANGED,
    ATTENTION_CREATED,
    ATTENTION_RESOLVED,
    DECISION_ANSWERED,
    DECISION_CREATED,
    TASK_BLOCKED,
    TASK_UPDATED,
)
from models.agent import Agent, AgentStatus
from models.attention import AttentionEvent, AttentionType
from models.base import utcnow
from models.decision import DecisionRequest, DecisionStatus
from models.task import Task, TaskStatus
from serialization import serialize


async def create_decision_request(db: AsyncSession, agent: Agent, task: Task | None, question: str, options: list[dict] | None = None, allow_custom_answer: bool = True, agent_session_id: uuid.UUID | None = None) -> DecisionRequest:
    """The blocking half of README 19.7's ask_human tool: the caller awaits until answer_decision resolves this row."""
    decision = build_decision_request(agent, task, question, options, allow_custom_answer, agent_session_id)
    db.add(decision)
    block_agent_and_task(agent, task)
    attention_event = build_decision_attention_event(agent, task, decision, question)
    db.add(attention_event)
    await commit(db)
    publish_decision_created(decision, agent, task, attention_event)
    return decision


def publish_decision_created(decision: DecisionRequest, agent: Agent, task: Task | None, attention_event: AttentionEvent) -> None:
    bus.publish(DECISION_CREATED, serialize(decision))
    bus.publish(AGENT_STATUS_CHANGED, serialize(agent))
    bus.publish(ATTENTION_CREATED, serialize(attention_event))
    if task is not None:
        bus.publish(TASK_BLOCKED, serialize(task))


def build_decision_request(
    agent: Agent, task: Task | None, question: str, options: list[dict] | None, allow_custom_answer: bool, agent_session_id: uuid.UUID | None
) -> DecisionRequest:
    return DecisionRequest(
        id=uuid.uuid4(),
        agent_id=agent.id,
        task_id=task.id if task else None,
        agent_session_id=agent_session_id,
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
    """The other half of the round trip (README 31.3). Claiming the row and deciding whether to unblock the agent are both done under a row lock, so two answers (or an answer racing an orphan cancellation) can't corrupt agent/task state."""
    decision = await claim_pending_decision(db, decision_id, DecisionStatus.ANSWERED, answer=answer)
    attention_event = await resolve_attention_event(db, decision)
    agent = await unblock_agent_and_task(db, decision.agent_id, decision.task_id)
    task = await db.get(Task, decision.task_id) if decision.task_id else None
    await commit(db)
    publish_decision_answered(decision, agent, task, attention_event)
    return decision


def publish_decision_answered(decision: DecisionRequest, agent: Agent, task: Task | None, attention_event: AttentionEvent | None) -> None:
    bus.publish(DECISION_ANSWERED, serialize(decision))
    bus.publish(AGENT_STATUS_CHANGED, serialize(agent))
    if attention_event is not None:
        bus.publish(ATTENTION_RESOLVED, serialize(attention_event))
    if task is not None:
        bus.publish(TASK_UPDATED, serialize(task))


async def cancel_pending_decisions_for_agent(db: AsyncSession, agent_id: uuid.UUID) -> list[DecisionRequest]:
    """Called when an agent's run is found dead (README 31.5 reconciliation): a decision nobody can still act on must not later "answer" and resurrect the agent as working."""
    query = select(DecisionRequest).where(DecisionRequest.agent_id == agent_id, DecisionRequest.status == DecisionStatus.PENDING)
    return await cancel_pending_decisions(db, query)


async def cancel_pending_decisions_for_session(db: AsyncSession, agent_session_id: uuid.UUID) -> list[DecisionRequest]:
    """Track B2.6: scoped to one session, not the whole agent -- an agent-wide cancel would also cancel a pending decision from a different, still-live session for the same agent."""
    query = select(DecisionRequest).where(DecisionRequest.agent_session_id == agent_session_id, DecisionRequest.status == DecisionStatus.PENDING)
    return await cancel_pending_decisions(db, query)


async def cancel_pending_decisions(db: AsyncSession, query) -> list[DecisionRequest]:
    pending = list((await db.execute(query)).scalars())
    cancelled, resolved_events = await cancel_and_resolve_all(db, pending)
    await commit(db)
    publish_resolved_attention_events(resolved_events)
    return cancelled


async def cancel_and_resolve_all(db: AsyncSession, pending: list[DecisionRequest]) -> tuple[list[DecisionRequest], list[AttentionEvent | None]]:
    cancelled = []
    resolved_events = []
    for decision in pending:
        claimed = await claim_pending_decision(db, decision.id, DecisionStatus.CANCELLED)
        resolved_events.append(await resolve_attention_event(db, claimed))
        cancelled.append(claimed)
    return cancelled, resolved_events


def publish_resolved_attention_events(events: list[AttentionEvent | None]) -> None:
    for event in events:
        if event is not None:
            bus.publish(ATTENTION_RESOLVED, serialize(event))


async def claim_pending_decision(db: AsyncSession, decision_id: uuid.UUID, new_status: DecisionStatus, answer: str | None = None) -> DecisionRequest:
    """One atomic UPDATE ... WHERE status = pending: whichever caller's answer/cancel wins, the loser gets a clear error instead of silently overwriting the winner."""
    values = {"status": new_status, "answered_at": utcnow()}
    if answer is not None:
        values["answer"] = answer
    stmt = update(DecisionRequest).where(DecisionRequest.id == decision_id, DecisionRequest.status == DecisionStatus.PENDING).values(**values)
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise ValueError(f"decision {decision_id} is not pending (already answered, cancelled, or missing)")
    return await db.get(DecisionRequest, decision_id)


async def resolve_attention_event(db: AsyncSession, decision: DecisionRequest) -> AttentionEvent | None:
    query = select(AttentionEvent).where(AttentionEvent.decision_request_id == decision.id)
    event = (await db.execute(query)).scalars().first()
    if event is not None:
        event.resolved = True
        event.resolved_at = utcnow()
    return event


async def unblock_agent_and_task(db: AsyncSession, agent_id: uuid.UUID, task_id: uuid.UUID | None) -> Agent:
    agent = (await db.execute(select(Agent).where(Agent.id == agent_id).with_for_update())).scalar_one()
    still_pending = await has_pending_decision(db, agent.id)
    agent.needs_attention = still_pending
    if still_pending:
        return agent
    agent.status = AgentStatus.WORKING
    if task_id is not None:
        task = await db.get(Task, task_id)
        task.status = TaskStatus.IN_PROGRESS
    return agent


async def has_pending_decision(db: AsyncSession, agent_id: uuid.UUID) -> bool:
    query = select(func.count()).select_from(DecisionRequest).where(
        DecisionRequest.agent_id == agent_id, DecisionRequest.status == DecisionStatus.PENDING
    )
    result = await db.execute(query)
    return result.scalar_one() > 0


async def list_pending_decisions(db: AsyncSession) -> list[DecisionRequest]:
    query = select(DecisionRequest).where(DecisionRequest.status == DecisionStatus.PENDING).order_by(DecisionRequest.created_at)
    return list((await db.execute(query)).scalars())
