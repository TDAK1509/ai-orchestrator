import uuid

from db import commit
from models.checkpoint import AgentCheckpoint
from models.memory import MemoryScope, MemorySourceType, MemoryType
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


async def extract_memories_from_checkpoint(db, checkpoint: AgentCheckpoint) -> list:
    """No model pass (README 32.2): the checkpoint's own fields become memories directly, since the agent already produced them as structured data."""
    records = [build_summary_memory(checkpoint), *build_field_memories(checkpoint)]
    for record in records:
        db.add(record)
    await commit(db)
    return records


def build_summary_memory(checkpoint: AgentCheckpoint):
    return build_checkpoint_memory(checkpoint, checkpoint.summary, MemoryType.TASK_SUMMARY)


def build_field_memories(checkpoint: AgentCheckpoint) -> list:
    typed_fields = [
        (checkpoint.decisions, MemoryType.DECISION),
        (checkpoint.discoveries, MemoryType.FACT),
        (checkpoint.risks, MemoryType.LESSON),
        (checkpoint.important_files, MemoryType.FACT),
    ]
    return [build_checkpoint_memory(checkpoint, content, type_) for values, type_ in typed_fields for content in values]


def build_checkpoint_memory(checkpoint: AgentCheckpoint, content: str, type_: MemoryType):
    return build_memory(
        MemoryScope.AGENT, content, type_, checkpoint.agent_id, checkpoint.task_id,
        importance=0.5, pinned=False, source_type=MemorySourceType.SYSTEM, source_id=str(checkpoint.id),
    )
