import re
import uuid
from datetime import UTC, timedelta

from sqlalchemy import or_, select

from db import commit
from models.base import utcnow
from models.memory import (
    MemoryProposal,
    MemoryProposalStatus,
    MemoryRecord,
    MemorySourceType,
    MemoryStatus,
)
from services.embedding_service import cosine_similarity

SIMILARITY_THRESHOLD = 0.92
CANDIDATE_LIMIT = 300
STALE_AFTER_DAYS = 30


async def list_pending_proposals(db) -> list[MemoryProposal]:
    query = select(MemoryProposal).where(MemoryProposal.status == MemoryProposalStatus.PENDING).order_by(MemoryProposal.created_at.desc())
    return list((await db.execute(query)).scalars())


async def generate_consolidation_proposals(db) -> list[MemoryProposal]:
    """A3.1/3: proposes; never applies. An exact duplicate (same content once normalized) is the one case safe to fold automatically -- there is no information to lose."""
    candidates = await find_proposal_candidates(db)
    existing_pairs = await find_existing_proposal_pairs(db)
    proposals = []
    for old, new in find_similar_pairs(candidates):
        await process_similar_pair(db, old, new, existing_pairs, proposals)
    return await save_proposals(db, proposals)


async def process_similar_pair(db, old: MemoryRecord, new: MemoryRecord, existing_pairs: set, proposals: list) -> None:
    if (old.id, new.id) in existing_pairs:
        return
    if normalize(old.content) == normalize(new.content):
        await supersede_with(db, old, new)
    else:
        proposals.append(build_proposal(old, new))


async def find_proposal_candidates(db) -> list[MemoryRecord]:
    query = build_proposal_candidate_query()
    return list((await db.execute(query)).scalars())


def build_proposal_candidate_query():
    return select(MemoryRecord).where(*proposal_eligibility_clauses()).order_by(MemoryRecord.created_at.asc()).limit(CANDIDATE_LIMIT)


def proposal_eligibility_clauses() -> tuple:
    """Never a human-authored or pinned record (A3.3): those are never superseded automatically."""
    return (
        MemoryRecord.status == MemoryStatus.ACTIVE,
        MemoryRecord.pinned.is_(False),
        MemoryRecord.embedding.isnot(None),
        or_(MemoryRecord.source_type.is_(None), MemoryRecord.source_type != MemorySourceType.HUMAN),
    )


async def find_existing_proposal_pairs(db) -> set[tuple[uuid.UUID, uuid.UUID]]:
    query = select(MemoryProposal.old_memory_id, MemoryProposal.new_memory_id).where(MemoryProposal.status == MemoryProposalStatus.PENDING)
    return set((await db.execute(query)).all())


def find_similar_pairs(candidates: list[MemoryRecord]):
    for index, old in enumerate(candidates):
        for new in candidates[index + 1 :]:
            if same_owner(old, new) and cosine_similarity(old.embedding, new.embedding) >= SIMILARITY_THRESHOLD:
                yield old, new


def same_owner(a: MemoryRecord, b: MemoryRecord) -> bool:
    return a.scope == b.scope and a.agent_id == b.agent_id and a.task_id == b.task_id


def normalize(content: str) -> str:
    return re.sub(r"\s+", " ", content).strip().lower()


def build_proposal(old: MemoryRecord, new: MemoryRecord) -> MemoryProposal:
    return MemoryProposal(id=uuid.uuid4(), old_memory_id=old.id, new_memory_id=new.id, similarity=cosine_similarity(old.embedding, new.embedding))


async def save_proposals(db, proposals: list[MemoryProposal]) -> list[MemoryProposal]:
    if not proposals:
        return []
    for proposal in proposals:
        db.add(proposal)
    await commit(db)
    return proposals


async def supersede_with(db, old: MemoryRecord, existing_new: MemoryRecord) -> None:
    """A3.2: points at an existing record instead of manufacturing a new one from content -- supersede_memory always creates a third record, which is wrong for deduping an already-inserted row."""
    old.status = MemoryStatus.SUPERSEDED
    old.superseded_by = existing_new.id
    await commit(db)


async def apply_proposal(db, proposal: MemoryProposal) -> None:
    old = await db.get(MemoryRecord, proposal.old_memory_id)
    new = await db.get(MemoryRecord, proposal.new_memory_id)
    await supersede_with(db, old, new)
    proposal.status = MemoryProposalStatus.APPLIED
    proposal.resolved_at = utcnow()
    await commit(db)


async def dismiss_proposal(db, proposal: MemoryProposal) -> None:
    proposal.status = MemoryProposalStatus.DISMISSED
    proposal.resolved_at = utcnow()
    await commit(db)


async def archive_stale_memories(db, stale_after_days: int = STALE_AFTER_DAYS) -> int:
    """importance <= 0.5, not < 0.5: every generated memory is created at exactly 0.5, so a strict < archives nothing (A3.4)."""
    cutoff = utcnow() - timedelta(days=stale_after_days)
    candidates = await find_stale_candidates(db)
    stale = [record for record in candidates if reference_time(record) < cutoff]
    for record in stale:
        record.status = MemoryStatus.ARCHIVED
    if stale:
        await commit(db)
    return len(stale)


async def find_stale_candidates(db) -> list[MemoryRecord]:
    query = select(MemoryRecord).where(
        MemoryRecord.status == MemoryStatus.ACTIVE,
        MemoryRecord.pinned.is_(False),
        MemoryRecord.importance <= 0.5,
        or_(MemoryRecord.source_type.is_(None), MemoryRecord.source_type != MemorySourceType.HUMAN),
    )
    return list((await db.execute(query)).scalars())


def reference_time(record: MemoryRecord):
    reference = record.last_accessed_at or record.created_at
    return reference.replace(tzinfo=UTC) if reference.tzinfo is None else reference
