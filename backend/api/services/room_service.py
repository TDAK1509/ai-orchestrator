import uuid

from sqlalchemy import select

from db import commit
from models.agent import Agent
from models.room import Room, RoomType

MAIN_ROOM_NAME = "Main Room"


async def ensure_main_room(db) -> Room:
    """Rule 1 (README 23): there is always a Main Room. Every agent not in a meeting belongs here."""
    room = await find_main_room(db)
    if room is not None:
        return room
    room = Room(id=uuid.uuid4(), name=MAIN_ROOM_NAME, type=RoomType.MAIN)
    db.add(room)
    await commit(db)
    return room


async def find_main_room(db) -> Room | None:
    query = select(Room).where(Room.type == RoomType.MAIN)
    return (await db.execute(query)).scalars().first()


async def move_agent_to_room(db, agent: Agent, room: Room) -> None:
    agent.room_id = room.id
    await commit(db)


async def list_rooms(db) -> list[Room]:
    return list((await db.execute(select(Room))).scalars())


async def list_room_agents(db, room_id: uuid.UUID) -> list[Agent]:
    return list((await db.execute(select(Agent).where(Agent.room_id == room_id))).scalars())
