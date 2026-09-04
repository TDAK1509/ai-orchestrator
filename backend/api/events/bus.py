import asyncio

QUEUE_MAXSIZE = 200


class EventBus:
    """In-process fan-out for a single backend process (README 24): no Redis, since this is a local, single-process tool, not a distributed deployment."""

    def __init__(self):
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def publish(self, event_type: str, data: dict) -> None:
        envelope = {"type": event_type, "data": data}
        for queue in list(self._subscribers):
            deliver(queue, envelope)


def deliver(queue: asyncio.Queue, envelope: dict) -> None:
    """A subscriber that can't keep up drops events instead of growing without bound; there is no durable replay guarantee here anyway (README 24 is served best-effort, not persisted)."""
    try:
        queue.put_nowait(envelope)
    except asyncio.QueueFull:
        pass


bus = EventBus()
