import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from auth import authorize_websocket
from events.bus import bus

router = APIRouter(tags=["events"])

HEARTBEAT_SECONDS = 30


@router.websocket("/ws")
async def stream_events_route(websocket: WebSocket):
    if not await authorize_websocket(websocket):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    queue = bus.subscribe()
    try:
        await relay_events(websocket, queue)
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(queue)


async def relay_events(websocket: WebSocket, queue: asyncio.Queue) -> None:
    while True:
        envelope = await next_envelope_or_heartbeat(queue)
        await websocket.send_json(envelope)


async def next_envelope_or_heartbeat(queue: asyncio.Queue) -> dict:
    """A truly idle client would otherwise hold its subscription forever: this bounds how long a dead connection survives to one heartbeat send, which fails fast on a closed socket."""
    try:
        return await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
    except TimeoutError:
        return {"type": "ping", "data": {}}
