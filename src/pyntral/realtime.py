"""Bounded, metadata-free invalidation signals for connected admin browsers.

A notification only means that some resource state may have changed. It never
includes record identifiers, field names or values. Client API reads are
still independently authenticated and scoped by the regular Pyntral backend.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable

from .events import EventTransport


class RealtimeNotifier:
    """Attach in-process listeners to the configured event transport.

    No durable delivery is promised. Cross-worker behavior depends on the
    transport's consumer topology. Signals are deliberately coalesced.
    """

    def __init__(self, bus: EventTransport, *, max_clients: int = 64):
        if max_clients < 1:
            raise ValueError("max_clients must be positive")
        self.bus = bus
        self.max_clients = max_clients
        self._clients = 0

    def listen(self) -> tuple[asyncio.Queue[None], Callable[[], None]]:
        if self._clients >= self.max_clients:
            raise RuntimeError("Too many realtime subscribers")
        queue: asyncio.Queue[None] = asyncio.Queue(maxsize=1)
        self._clients += 1

        def signal(_event: Any) -> None:
            if queue.empty():
                queue.put_nowait(None)

        subscriptions = [
            self.bus.subscribe("resource.*", signal),
            self.bus.subscribe("action.collection_executed", signal),
            self.bus.subscribe("action.executed", signal),
        ]
        closed = False

        def close() -> None:
            nonlocal closed
            if closed:
                return
            closed = True
            for unsubscribe in subscriptions:
                unsubscribe()
            self._clients -= 1

        return queue, close
