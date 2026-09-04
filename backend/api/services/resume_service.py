import uuid

from sqlalchemy import select, update

from db import commit
from models.base import utcnow
from models.decision import DecisionRequest, DecisionStatus
from models.session import AgentSession
from services.decision_service import cancel_pending_decisions_for_session

MAX_RESUME_ATTEMPTS = 3
RESUME_HEADER = "You were interrupted before finishing this task (the backend restarted). Continue from where you left off."


async def mark_resume_pending(db, agent_session: AgentSession, prompt: str) -> None:
    agent_session.resume_pending = True
    agent_session.resume_prompt = prompt
    await commit(db)


async def clear_resume_pending(db, agent_session: AgentSession) -> None:
    agent_session.resume_pending = False
    agent_session.resume_prompt = None
    await commit(db)


async def claim_next_resume_attempt(db, agent_session_id: uuid.UUID) -> bool:
    """One atomic UPDATE (B2.2): counting ExecutionRun rows would miss an attempt that failed before a row ever existed."""
    stmt = (
        update(AgentSession)
        .where(AgentSession.id == agent_session_id, AgentSession.resume_pending.is_(True), AgentSession.resume_attempts < MAX_RESUME_ATTEMPTS)
        .values(resume_attempts=AgentSession.resume_attempts + 1, resume_claimed_at=utcnow())
    )
    result = await db.execute(stmt)
    await commit(db)
    return result.rowcount > 0


async def build_resume_prompt(db, agent_session: AgentSession) -> str:
    """B2.6: cancel decisions nobody can act on any more, and replay the most recent answered one -- the polling process that would have delivered it is gone, so there is no way to know whether the answer ever reached Claude."""
    await cancel_pending_decisions_for_session(db, agent_session.id)
    replay = await render_last_answered_decision(db, agent_session.id)
    return f"{RESUME_HEADER}\n\n{replay}" if replay else RESUME_HEADER


async def render_last_answered_decision(db, agent_session_id: uuid.UUID) -> str:
    decision = await find_last_answered_decision(db, agent_session_id)
    if decision is None:
        return ""
    return f'You previously asked "{decision.question}" and may already have seen this answer (treat it as possibly already acted on): {decision.answer}'


async def find_last_answered_decision(db, agent_session_id: uuid.UUID) -> DecisionRequest | None:
    query = (
        select(DecisionRequest)
        .where(DecisionRequest.agent_session_id == agent_session_id, DecisionRequest.status == DecisionStatus.ANSWERED)
        .order_by(DecisionRequest.answered_at.desc())
        .limit(1)
    )
    return (await db.execute(query)).scalars().first()


async def find_resume_pending_sessions(db) -> list[AgentSession]:
    query = select(AgentSession).where(AgentSession.resume_pending.is_(True))
    return list((await db.execute(query)).scalars())
