import uuid

from sqlalchemy import select, update

from db import commit
from events.bus import bus
from events.schema import MEMORY_CREATED
from models.base import utcnow
from models.checkpoint import AgentCheckpoint
from models.memory import MemoryRecord, MemoryScope, MemorySourceType, MemoryType
from serialization import serialize
from services.memory_service import build_memory


async def create_checkpoint(db, agent_id: uuid.UUID, agent_session_id: uuid.UUID, summary: str, task_id: uuid.UUID | None = None, decisions: list[str] | None = None, discoveries: list[str] | None = None, important_files: list[str] | None = None, unfinished_work: list[str] | None = None, blockers: list[str] | None = None, risks: list[str] | None = None, branch: str | None = None, head_sha: str | None = None, test_status: str | None = None) -> AgentCheckpoint:
    checkpoint = AgentCheckpoint(
        id=uuid.uuid4(), agent_id=agent_id, task_id=task_id, agent_session_id=agent_session_id, summary=summary,
        decisions=decisions or [], discoveries=discoveries or [], important_files=important_files or [],
        unfinished_work=unfinished_work or [], blockers=blockers or [], risks=risks or [],
        branch=branch, head_sha=head_sha, test_status=test_status,
    )
    db.add(checkpoint)
    await commit(db)
    return checkpoint


async def extract_memories_on_task_completion(db, agent_id: uuid.UUID, task_id: uuid.UUID, title: str, branch: str | None, landed_sha: str | None) -> list:
    """A1: the agent's own checkpoint is preferred (structured, no model pass); a task that never called write_checkpoint still leaves one fact behind instead of nothing."""
    checkpoint = await find_latest_unused_checkpoint(db, agent_id)
    if checkpoint is not None:
        return await extract_memories_from_checkpoint(db, checkpoint)
    return [await create_fallback_task_summary(db, agent_id, task_id, title, branch, landed_sha)]


async def find_latest_unused_checkpoint(db, agent_id: uuid.UUID) -> AgentCheckpoint | None:
    query = (
        select(AgentCheckpoint)
        .where(AgentCheckpoint.agent_id == agent_id, AgentCheckpoint.used_at.is_(None))
        .order_by(AgentCheckpoint.created_at.desc())
        .limit(1)
    )
    return (await db.execute(query)).scalars().first()


async def extract_memories_from_checkpoint(db, checkpoint: AgentCheckpoint) -> list:
    """No model pass (README 32.2): the checkpoint's own fields become memories directly. A1.2: the claim and the memory inserts share this one commit, so a racing caller can't extract the same checkpoint twice."""
    if not await claim_checkpoint(db, checkpoint.id):
        raise ValueError(f"checkpoint {checkpoint.id} was already consumed")
    checkpoint.used_at = utcnow()
    records = [build_summary_memory(checkpoint), *build_field_memories(checkpoint)]
    for record in records:
        db.add(record)
    await commit(db)
    publish_memories_created(records)
    return records


async def claim_checkpoint(db, checkpoint_id: uuid.UUID) -> bool:
    stmt = update(AgentCheckpoint).where(AgentCheckpoint.id == checkpoint_id, AgentCheckpoint.used_at.is_(None)).values(used_at=utcnow())
    result = await db.execute(stmt)
    return result.rowcount > 0


def build_summary_memory(checkpoint: AgentCheckpoint):
    return build_checkpoint_memory(checkpoint, checkpoint.summary, MemoryType.TASK_SUMMARY)


def build_field_memories(checkpoint: AgentCheckpoint) -> list:
    typed_fields = [
        (checkpoint.decisions, MemoryType.DECISION),
        (checkpoint.discoveries, MemoryType.FACT),
        (checkpoint.blockers, MemoryType.LESSON),
        (checkpoint.risks, MemoryType.LESSON),
        (checkpoint.important_files, MemoryType.FACT),
    ]
    return [build_checkpoint_memory(checkpoint, content, type_) for values, type_ in typed_fields for content in values]


def build_checkpoint_memory(checkpoint: AgentCheckpoint, content: str, type_: MemoryType):
    return build_memory(
        MemoryScope.AGENT, content, type_, checkpoint.agent_id, checkpoint.task_id,
        importance=0.5, pinned=False, source_type=MemorySourceType.AGENT, source_id=str(checkpoint.id),
    )


async def create_fallback_task_summary(db, agent_id: uuid.UUID, task_id: uuid.UUID, title: str, branch: str | None, landed_sha: str | None) -> MemoryRecord:
    """A1.3/4: AGENT-scoped, since MemoryScope.TASK is unreachable today."""
    content = describe_landed_task(title, branch, landed_sha)
    record = build_memory(MemoryScope.AGENT, content, MemoryType.TASK_SUMMARY, agent_id, task_id, importance=0.5, pinned=False, source_type=MemorySourceType.TASK, source_id=str(task_id))
    db.add(record)
    await commit(db)
    publish_memories_created([record])
    return record


def describe_landed_task(title: str, branch: str | None, landed_sha: str | None) -> str:
    parts = [f"Completed task: {title}"]
    if branch:
        parts.append(f"branch {branch}")
    if landed_sha:
        parts.append(f"landed at {landed_sha}")
    return ", ".join(parts)


def publish_memories_created(records: list[MemoryRecord]) -> None:
    for record in records:
        bus.publish(MEMORY_CREATED, serialize(record))
