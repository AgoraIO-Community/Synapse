from __future__ import annotations

import asyncio

from .store import BlackboardWriteEvent


class SubscriptionManager:
    def __init__(self) -> None:
        self._queues: list[asyncio.Queue[BlackboardWriteEvent]] = []

    def subscribe(self) -> asyncio.Queue[BlackboardWriteEvent]:
        queue: asyncio.Queue[BlackboardWriteEvent] = asyncio.Queue()
        self._queues.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[BlackboardWriteEvent]) -> None:
        if queue in self._queues:
            self._queues.remove(queue)

    async def publish(self, event: BlackboardWriteEvent) -> None:
        for queue in list(self._queues):
            await queue.put(event)
