import uuid
from datetime import UTC

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import commit
from models.base import utcnow
from models.memory import (
    MemoryRecord,
    MemoryScope,
    MemorySourceType,
    MemoryStatus,
    MemoryType,
)

RETRIEVAL_LIMIT = 20


async def create_human_memory(db: AsyncSession, scope: MemoryScope, content: str, type_: MemoryType, agent_id: uuid.UUID | None = None, task_id: uuid.UUID | None = None) -> MemoryRecord:
    """A human memory is never superseded automatically (README 32.2) and always carries maximum importance."""
    return await create_memory(db, scope, content, type_, agent_id, task_id, importance=1.0, source_type=MemorySourceType.HUMAN)


async def pin_memory(db: AsyncSession, record: MemoryRecord) -> None:
    record.pinned = True
    await commit(db)


async def unpin_memory(db: AsyncSession, record: MemoryRecord) -> None:
    record.pinned = False
    await commit(db)


async def archive_memory(db: AsyncSession, record: MemoryRecord) -> None:
    record.status = MemoryStatus.ARCHIVED
    await commit(db)


async def supersede_memory(db: AsyncSession, old: MemoryRecord, content: str, type_: MemoryType, source_type: MemorySourceType | None = None, source_id: str | None = None) -> MemoryRecord:
    """One commit for both rows (README 32.4): a crash or concurrent read between two separate commits could see the old and new record both active at once."""
    new_record = build_memory(old.scope, content, type_, old.agent_id, old.task_id, old.importance, False, source_type, source_id)
    db.add(new_record)
    old.status = MemoryStatus.SUPERSEDED
    old.superseded_by = new_record.id
    await commit(db)
    return new_record


async def create_memory(db: AsyncSession, scope: MemoryScope, content: str, type_: MemoryType, agent_id: uuid.UUID | None = None, task_id: uuid.UUID | None = None, importance: float = 0.5, pinned: bool = False, source_type: MemorySourceType | None = None, source_id: str | None = None) -> MemoryRecord:
    record = build_memory(scope, content, type_, agent_id, task_id, importance, pinned, source_type, source_id)
    db.add(record)
    await commit(db)
    return record


def build_memory(scope: MemoryScope, content: str, type_: MemoryType, agent_id: uuid.UUID | None, task_id: uuid.UUID | None, importance: float, pinned: bool, source_type: MemorySourceType | None, source_id: str | None) -> MemoryRecord:
    require_valid_scope(scope, agent_id, task_id)
    return MemoryRecord(
        id=uuid.uuid4(), scope=scope, agent_id=agent_id, task_id=task_id, type=type_, content=content,
        importance=importance, pinned=pinned, source_type=source_type, source_id=source_id,
    )


def require_valid_scope(scope: MemoryScope, agent_id: uuid.UUID | None, task_id: uuid.UUID | None) -> None:
    """A workspace record with an agent_id (or an agent record without one) is a confusing, invalid state (README 32.1): scope and owner must agree."""
    if scope == MemoryScope.WORKSPACE and agent_id is not None:
        raise ValueError("a workspace-scoped memory must not have an agent_id")
    if scope == MemoryScope.AGENT and agent_id is None:
        raise ValueError("an agent-scoped memory requires an agent_id")
    if scope == MemoryScope.TASK and task_id is None:
        raise ValueError("a task-scoped memory requires a task_id")


async def list_workspace_memories(db: AsyncSession, include_archived: bool = False) -> list[MemoryRecord]:
    query = select(MemoryRecord).where(MemoryRecord.scope == MemoryScope.WORKSPACE)
    if not include_archived:
        query = query.where(MemoryRecord.status != MemoryStatus.ARCHIVED)
    return list((await db.execute(query.order_by(MemoryRecord.created_at.desc()))).scalars())


async def list_agent_memories(db: AsyncSession, agent_id: uuid.UUID, include_archived: bool = False) -> list[MemoryRecord]:
    query = select(MemoryRecord).where(MemoryRecord.scope == MemoryScope.AGENT, MemoryRecord.agent_id == agent_id)
    if not include_archived:
        query = query.where(MemoryRecord.status != MemoryStatus.ARCHIVED)
    return list((await db.execute(query.order_by(MemoryRecord.created_at.desc()))).scalars())


async def retrieve_context_memories(db: AsyncSession, agent_id: uuid.UUID, query_text: str, limit: int = RETRIEVAL_LIMIT) -> list[MemoryRecord]:
    """Pinned memory has its own budget (README 32.3): it's always included, never crowded out by whatever scores highest below."""
    pinned = await list_pinned_for_agent(db, agent_id)
    candidates = await list_unpinned_active_for_agent(db, agent_id)
    ranked = sorted(candidates, key=lambda record: score_memory(record, query_text), reverse=True)
    retrieved = pinned + ranked[:limit]
    await touch_memories(db, retrieved)
    return retrieved


async def list_pinned_for_agent(db: AsyncSession, agent_id: uuid.UUID) -> list[MemoryRecord]:
    return await list_active_for_agent(db, agent_id, pinned=True)


async def list_unpinned_active_for_agent(db: AsyncSession, agent_id: uuid.UUID) -> list[MemoryRecord]:
    return await list_active_for_agent(db, agent_id, pinned=False)


async def list_active_for_agent(db: AsyncSession, agent_id: uuid.UUID, pinned: bool) -> list[MemoryRecord]:
    in_scope = or_(MemoryRecord.scope == MemoryScope.WORKSPACE, and_(MemoryRecord.scope == MemoryScope.AGENT, MemoryRecord.agent_id == agent_id))
    query = select(MemoryRecord).where(MemoryRecord.status == MemoryStatus.ACTIVE, MemoryRecord.pinned.is_(pinned), in_scope)
    return list((await db.execute(query)).scalars())


def score_memory(record: MemoryRecord, query_text: str) -> float:
    """No embedding provider is wired up, so "similarity" is keyword overlap, not the cosine similarity README 32.3 specifies -- same weights, a cruder signal."""
    similarity = keyword_overlap_score(record.content, query_text)
    return 0.6 * similarity + 0.25 * record.importance + 0.15 * recency_score(record)


def keyword_overlap_score(content: str, query_text: str) -> float:
    query_words = set(query_text.lower().split())
    if not query_words:
        return 0.0
    content_words = set(content.lower().split())
    return len(content_words & query_words) / len(query_words)


def recency_score(record: MemoryRecord) -> float:
    """SQLite round-trips DateTime(timezone=True) as naive, unlike Postgres: normalize before subtracting from utcnow()."""
    reference = record.last_accessed_at or record.created_at
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=UTC)
    age_days = (utcnow() - reference).total_seconds() / 86400
    return 1.0 / (1.0 + age_days)


async def touch_memories(db: AsyncSession, records: list[MemoryRecord]) -> None:
    if not records:
        return
    now = utcnow()
    for record in records:
        record.last_accessed_at = now
    await commit(db)
