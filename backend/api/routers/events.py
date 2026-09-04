from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from events.bus import bus

router = APIRouter(tags=["events"])


@router.websocket("/ws")
async def stream_events_route(websocket: WebSocket):
    await websocket.accept()
    queue = bus.subscribe()
    try:
        await relay_events(websocket, queue)
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(queue)


async def relay_events(websocket: WebSocket, queue) -> None:
    while True:
        envelope = await queue.get()
        await websocket.send_json(envelope)
