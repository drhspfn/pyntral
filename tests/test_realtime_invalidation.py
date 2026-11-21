"""No field or record data travels in realtime invalidation messages."""
from __future__ import annotations

import asyncio
import pytest

from pyntral import InMemoryEventBus, ResourceUpdated, FieldRef
from pyntral.realtime import RealtimeNotifier


@pytest.mark.asyncio
async def test_bounded_broadcast_coalesces_and_unsubscribes():
    bus = InMemoryEventBus()
    notifier = RealtimeNotifier(bus, max_clients=2)
    first, close_first = notifier.listen()
    second, close_second = notifier.listen()
    with pytest.raises(RuntimeError, match="Too many realtime subscribers"):
        notifier.listen()

    await bus.publish(ResourceUpdated(resource="users", record_id="42", actor_id="admin",
                                      fields=(FieldRef(name="password_hash", kind="string"),)))
    await bus.publish(ResourceUpdated(resource="users", record_id="43"))
    assert first.qsize() == 1 and second.qsize() == 1  # coalesced, not queued per event
    assert await asyncio.wait_for(first.get(), 0.1) is None  # no private data
    assert await asyncio.wait_for(second.get(), 0.1) is None

    close_first()
    close_first()  # idempotent
    await bus.publish(ResourceUpdated(resource="users", record_id="44"))
    assert first.empty() and second.qsize() == 1
    close_second()
    third, close_third = notifier.listen()
    close_third()
