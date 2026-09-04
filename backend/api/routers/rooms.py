import uuid

from fastapi import APIRouter, Depends

from deps import get_db
from serialization import serialize
from services.room_service import list_room_agents, list_rooms

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.get("")
async def list_rooms_route(db=Depends(get_db)):
    return [serialize(room) for room in await list_rooms(db)]


@router.get("/{room_id}/agents")
async def list_room_agents_route(room_id: uuid.UUID, db=Depends(get_db)):
    return [serialize(agent) for agent in await list_room_agents(db, room_id)]
