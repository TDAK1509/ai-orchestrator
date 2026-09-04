import asyncio


class EventBus:
    """In-process fan-out for a single backend process (README 24): no Redis, since this is a local, single-process tool, not a distributed deployment."""

    def __init__(self):
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def publish(self, event_type: str, data: dict) -> None:
        envelope = {"type": event_type, "data": data}
        for queue in list(self._subscribers):
            queue.put_nowait(envelope)


bus = EventBus()
