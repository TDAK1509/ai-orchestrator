import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import get_db
from events.bus import bus
from events.schema import MEMORY_CREATED
from lookups import get_active_or_404, get_or_404
from models.memory import MemoryProposal, MemoryRecord, MemoryScope, MemoryType
from models.team import Team
from serialization import serialize
from services.memory_consolidation_service import (
    apply_proposal,
    dismiss_proposal,
    list_pending_proposals,
)
from services.memory_service import (
    archive_memory,
    create_human_memory,
    list_agent_memories,
    list_team_memories,
    list_workspace_memories,
    pin_memory,
    promote_memory_to_workspace,
    unpin_memory,
)

router = APIRouter(prefix="/memory", tags=["memory"])


class CreateMemoryBody(BaseModel):
    scope: MemoryScope
    content: str
    type: MemoryType
    agent_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None


@router.get("/workspace")
async def list_workspace_memories_route(db=Depends(get_db)):
    return [serialize_memory(record) for record in await list_workspace_memories(db)]


def serialize_memory(record: MemoryRecord) -> dict:
    """codex P2: the generic serializer emits every mapped column, including the ~384-float embedding vector nothing in the UI uses -- drop it from the API response, not just from the frontend type."""
    payload = serialize(record)
    payload.pop("embedding", None)
    return payload


@router.get("/agents/{agent_id}")
async def list_agent_memories_route(agent_id: uuid.UUID, db=Depends(get_db)):
    return [serialize_memory(record) for record in await list_agent_memories(db, agent_id)]


@router.get("/teams/{team_id}")
async def list_team_memories_route(team_id: uuid.UUID, db=Depends(get_db)):
    await get_or_404(db, Team, team_id, "team")
    return [serialize_memory(record) for record in await list_team_memories(db, team_id)]


@router.post("", status_code=201)
async def create_memory_route(body: CreateMemoryBody, db=Depends(get_db)):
    if body.team_id is not None:
        await get_active_or_404(db, Team, body.team_id, "team")
    record = await create_human_memory(db, body.scope, body.content, body.type, body.agent_id, body.task_id, body.team_id)
    bus.publish(MEMORY_CREATED, serialize_memory(record))
    return serialize_memory(record)


@router.post("/{memory_id}/pin")
async def pin_memory_route(memory_id: uuid.UUID, db=Depends(get_db)):
    record = await get_or_404(db, MemoryRecord, memory_id, "memory record")
    await pin_memory(db, record)
    return serialize_memory(record)


@router.post("/{memory_id}/unpin")
async def unpin_memory_route(memory_id: uuid.UUID, db=Depends(get_db)):
    record = await get_or_404(db, MemoryRecord, memory_id, "memory record")
    await unpin_memory(db, record)
    return serialize_memory(record)


@router.post("/{memory_id}/archive")
async def archive_memory_route(memory_id: uuid.UUID, db=Depends(get_db)):
    record = await get_or_404(db, MemoryRecord, memory_id, "memory record")
    await archive_memory(db, record)
    return serialize_memory(record)


@router.post("/{memory_id}/promote")
async def promote_memory_route(memory_id: uuid.UUID, db=Depends(get_db)):
    record = await get_or_404(db, MemoryRecord, memory_id, "memory record")
    await promote_memory_to_workspace(db, record)
    return serialize_memory(record)


@router.get("/proposals")
async def list_proposals_route(db=Depends(get_db)):
    return [serialize(proposal) for proposal in await list_pending_proposals(db)]


@router.post("/proposals/{proposal_id}/apply")
async def apply_proposal_route(proposal_id: uuid.UUID, db=Depends(get_db)):
    proposal = await get_or_404(db, MemoryProposal, proposal_id, "memory proposal")
    await apply_proposal(db, proposal)
    return serialize(proposal)


@router.post("/proposals/{proposal_id}/dismiss")
async def dismiss_proposal_route(proposal_id: uuid.UUID, db=Depends(get_db)):
    proposal = await get_or_404(db, MemoryProposal, proposal_id, "memory proposal")
    await dismiss_proposal(db, proposal)
    return serialize(proposal)
