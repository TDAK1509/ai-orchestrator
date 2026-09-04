import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import get_db
from events.bus import bus
from events.schema import MEMORY_CREATED
from lookups import get_or_404
from models.memory import MemoryProposal, MemoryRecord, MemoryScope, MemoryType
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


@router.get("/workspace")
async def list_workspace_memories_route(db=Depends(get_db)):
    return [serialize(record) for record in await list_workspace_memories(db)]


@router.get("/agents/{agent_id}")
async def list_agent_memories_route(agent_id: uuid.UUID, db=Depends(get_db)):
    return [serialize(record) for record in await list_agent_memories(db, agent_id)]


@router.post("", status_code=201)
async def create_memory_route(body: CreateMemoryBody, db=Depends(get_db)):
    record = await create_human_memory(db, body.scope, body.content, body.type, body.agent_id, body.task_id)
    bus.publish(MEMORY_CREATED, serialize(record))
    return serialize(record)


@router.post("/{memory_id}/pin")
async def pin_memory_route(memory_id: uuid.UUID, db=Depends(get_db)):
    record = await get_or_404(db, MemoryRecord, memory_id, "memory record")
    await pin_memory(db, record)
    return serialize(record)


@router.post("/{memory_id}/unpin")
async def unpin_memory_route(memory_id: uuid.UUID, db=Depends(get_db)):
    record = await get_or_404(db, MemoryRecord, memory_id, "memory record")
    await unpin_memory(db, record)
    return serialize(record)


@router.post("/{memory_id}/archive")
async def archive_memory_route(memory_id: uuid.UUID, db=Depends(get_db)):
    record = await get_or_404(db, MemoryRecord, memory_id, "memory record")
    await archive_memory(db, record)
    return serialize(record)


@router.post("/{memory_id}/promote")
async def promote_memory_route(memory_id: uuid.UUID, db=Depends(get_db)):
    record = await get_or_404(db, MemoryRecord, memory_id, "memory record")
    await promote_memory_to_workspace(db, record)
    return serialize(record)


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
