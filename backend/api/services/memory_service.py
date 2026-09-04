import uuid
from datetime import UTC

from sqlalchemy import and_, func, or_, select
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
from services.embedding_service import cosine_similarity, embed_text

RETRIEVAL_LIMIT = 20
CANDIDATE_TOP_K = 30
SIMILARITY_SCAN_CAP = 500


async def create_human_memory(db: AsyncSession, scope: MemoryScope, content: str, type_: MemoryType, agent_id: uuid.UUID | None = None, task_id: uuid.UUID | None = None, team_id: uuid.UUID | None = None) -> MemoryRecord:
    """A human memory is never superseded automatically (README 32.2) and always carries maximum importance."""
    return await create_memory(db, scope, content, type_, agent_id, task_id, importance=1.0, source_type=MemorySourceType.HUMAN, team_id=team_id)


async def pin_memory(db: AsyncSession, record: MemoryRecord) -> None:
    record.pinned = True
    await commit(db)


async def unpin_memory(db: AsyncSession, record: MemoryRecord) -> None:
    record.pinned = False
    await commit(db)


async def archive_memory(db: AsyncSession, record: MemoryRecord) -> None:
    record.status = MemoryStatus.ARCHIVED
    await commit(db)


async def promote_memory_to_workspace(db: AsyncSession, record: MemoryRecord) -> MemoryRecord:
    """Sharing (A1): the only way to move a private fact into workspace memory today is typing a new one by hand -- this promotes the agent's own instead."""
    if record.scope != MemoryScope.AGENT:
        raise ValueError(f"memory {record.id} is not agent-scoped (scope={record.scope.value})")
    record.scope = MemoryScope.WORKSPACE
    record.agent_id = None
    record.team_id = None
    await commit(db)
    return record


async def supersede_memory(db: AsyncSession, old: MemoryRecord, content: str, type_: MemoryType, source_type: MemorySourceType | None = None, source_id: str | None = None) -> MemoryRecord:
    """One commit for both rows (README 32.4): a crash or concurrent read between two separate commits could see the old and new record both active at once."""
    new_record = build_memory(old.scope, content, type_, old.agent_id, old.task_id, old.importance, False, source_type, source_id, team_id=old.team_id)
    db.add(new_record)
    old.status = MemoryStatus.SUPERSEDED
    old.superseded_by = new_record.id
    await commit(db)
    return new_record


async def create_memory(db: AsyncSession, scope: MemoryScope, content: str, type_: MemoryType, agent_id: uuid.UUID | None = None, task_id: uuid.UUID | None = None, importance: float = 0.5, pinned: bool = False, source_type: MemorySourceType | None = None, source_id: str | None = None, team_id: uuid.UUID | None = None) -> MemoryRecord:
    record = build_memory(scope, content, type_, agent_id, task_id, importance, pinned, source_type, source_id, team_id)
    db.add(record)
    await commit(db)
    return record


def build_memory(scope: MemoryScope, content: str, type_: MemoryType, agent_id: uuid.UUID | None, task_id: uuid.UUID | None, importance: float, pinned: bool, source_type: MemorySourceType | None, source_id: str | None, team_id: uuid.UUID | None = None) -> MemoryRecord:
    require_valid_scope(scope, agent_id, task_id, team_id)
    return MemoryRecord(
        id=uuid.uuid4(), scope=scope, agent_id=agent_id, task_id=task_id, team_id=team_id, type=type_, content=content,
        importance=importance, pinned=pinned, source_type=source_type, source_id=source_id,
    )


def require_valid_scope(scope: MemoryScope, agent_id: uuid.UUID | None, task_id: uuid.UUID | None, team_id: uuid.UUID | None = None) -> None:
    """Scope and owner must agree, in both directions (README 32.1): the scope's own owner field is present, and no other owner field is set."""
    require_owner_present(scope, agent_id, task_id, team_id)
    require_no_extraneous_owner(scope, agent_id, task_id, team_id)


def require_owner_present(scope: MemoryScope, agent_id: uuid.UUID | None, task_id: uuid.UUID | None, team_id: uuid.UUID | None) -> None:
    if scope == MemoryScope.AGENT and agent_id is None:
        raise ValueError("an agent-scoped memory requires an agent_id")
    if scope == MemoryScope.TEAM and team_id is None:
        raise ValueError("a team-scoped memory requires a team_id")
    if scope == MemoryScope.TASK and task_id is None:
        raise ValueError("a task-scoped memory requires a task_id")


def require_no_extraneous_owner(scope: MemoryScope, agent_id: uuid.UUID | None, task_id: uuid.UUID | None, team_id: uuid.UUID | None) -> None:
    if scope == MemoryScope.WORKSPACE and (agent_id is not None or team_id is not None):
        raise ValueError("a workspace-scoped memory must not have an agent_id or team_id")
    if scope == MemoryScope.AGENT and team_id is not None:
        raise ValueError("an agent-scoped memory must not have a team_id")
    if scope == MemoryScope.TEAM and (agent_id is not None or task_id is not None):
        raise ValueError("a team-scoped memory must not have an agent_id or task_id")


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


async def list_team_memories(db: AsyncSession, team_id: uuid.UUID, include_archived: bool = False) -> list[MemoryRecord]:
    query = select(MemoryRecord).where(MemoryRecord.scope == MemoryScope.TEAM, MemoryRecord.team_id == team_id)
    if not include_archived:
        query = query.where(MemoryRecord.status != MemoryStatus.ARCHIVED)
    return list((await db.execute(query.order_by(MemoryRecord.created_at.desc()))).scalars())


async def retrieve_context_memories(db: AsyncSession, agent_id: uuid.UUID, query_text: str, task_id: uuid.UUID | None = None, team_id: uuid.UUID | None = None, limit: int = RETRIEVAL_LIMIT) -> list[MemoryRecord]:
    """Pinned memory has its own budget (README 32.3): always included, never crowded out by whatever scores highest below. A2.4: the candidate set is a union of top-K by recency, importance and vector similarity, not "newest N" -- that would silently drop an old, highly relevant record before it is ever scored."""
    pinned = await list_pinned_for_agent(db, agent_id, task_id, team_id)
    query_embedding = await embed_text(query_text)
    candidates = await build_candidate_set(db, agent_id, task_id, team_id, query_embedding)
    ranked = sorted(candidates, key=lambda record: score_memory(record, query_text, query_embedding), reverse=True)
    retrieved = pinned + ranked[:limit]
    await touch_memories(db, retrieved)
    return retrieved


async def list_pinned_for_agent(db: AsyncSession, agent_id: uuid.UUID, task_id: uuid.UUID | None = None, team_id: uuid.UUID | None = None) -> list[MemoryRecord]:
    query = select(MemoryRecord).where(MemoryRecord.status == MemoryStatus.ACTIVE, MemoryRecord.pinned.is_(True), in_scope_clause(agent_id, task_id, team_id))
    return list((await db.execute(query)).scalars())


def in_scope_clause(agent_id: uuid.UUID, task_id: uuid.UUID | None, team_id: uuid.UUID | None = None):
    """A2.4: also true for a MemoryScope.TASK row scoped to this task -- dead before, since nothing accepted a task_id to filter by. team_id=None reproduces the pre-team clause exactly, so a teamless agent is unaffected."""
    clauses = [MemoryRecord.scope == MemoryScope.WORKSPACE, and_(MemoryRecord.scope == MemoryScope.AGENT, MemoryRecord.agent_id == agent_id)]
    if team_id is not None:
        clauses.append(and_(MemoryRecord.scope == MemoryScope.TEAM, MemoryRecord.team_id == team_id))
    if task_id is not None:
        clauses.append(and_(MemoryRecord.scope == MemoryScope.TASK, MemoryRecord.task_id == task_id))
    return or_(*clauses)


async def build_candidate_set(db: AsyncSession, agent_id: uuid.UUID, task_id: uuid.UUID | None, team_id: uuid.UUID | None, query_embedding: list[float]) -> list[MemoryRecord]:
    groups = [
        await list_unpinned_active_ordered(db, agent_id, task_id, team_id, recency_order()),
        await list_unpinned_active_ordered(db, agent_id, task_id, team_id, MemoryRecord.importance.desc()),
        await list_top_by_similarity(db, agent_id, task_id, team_id, query_embedding),
    ]
    return dedupe_by_id(record for group in groups for record in group)


def recency_order():
    return func.coalesce(MemoryRecord.last_accessed_at, MemoryRecord.created_at).desc()


def dedupe_by_id(records) -> list[MemoryRecord]:
    seen: dict[uuid.UUID, MemoryRecord] = {}
    for record in records:
        seen.setdefault(record.id, record)
    return list(seen.values())


async def list_unpinned_active_ordered(db: AsyncSession, agent_id: uuid.UUID, task_id: uuid.UUID | None, team_id: uuid.UUID | None, order_clause, limit: int = CANDIDATE_TOP_K) -> list[MemoryRecord]:
    query = (
        select(MemoryRecord)
        .where(MemoryRecord.status == MemoryStatus.ACTIVE, MemoryRecord.pinned.is_(False), in_scope_clause(agent_id, task_id, team_id))
        .order_by(order_clause)
        .limit(limit)
    )
    return list((await db.execute(query)).scalars())


async def list_top_by_similarity(db: AsyncSession, agent_id: uuid.UUID, task_id: uuid.UUID | None, team_id: uuid.UUID | None, query_embedding: list[float], limit: int = CANDIDATE_TOP_K) -> list[MemoryRecord]:
    """A2.6: brute-force cosine over embedded candidates, not an ANN index -- one local user's corpus is small enough that this stays fast (A2.6 note); pgvector can come later behind a capability check."""
    query = (
        select(MemoryRecord)
        .where(MemoryRecord.status == MemoryStatus.ACTIVE, MemoryRecord.pinned.is_(False), MemoryRecord.embedding.isnot(None), in_scope_clause(agent_id, task_id, team_id))
        .limit(SIMILARITY_SCAN_CAP)
    )
    embedded = list((await db.execute(query)).scalars())
    ranked = sorted(embedded, key=lambda record: cosine_similarity(record.embedding, query_embedding), reverse=True)
    return ranked[:limit]


def score_memory(record: MemoryRecord, query_text: str, query_embedding: list[float]) -> float:
    """A2.5: falls back to keyword overlap for a row the embedding sweep hasn't reached yet, so it stays scoreable instead of always losing to cosine-scored rows."""
    similarity = cosine_similarity(record.embedding, query_embedding) if record.embedding else keyword_overlap_score(record.content, query_text)
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
