"""Broker-neutral event contract and strict, metadata-only wire codec."""
from __future__ import annotations

import json
from typing import Any

from ..events import (
    ActionExecuted, CollectionActionExecuted, AdminEvent, CustomEvent, DeliveryReport, InMemoryEventBus,
    LoginFailed, LoginSucceeded, LogoutSucceeded, ResourceCreated, ResourceDeleted,
    ResourceUpdated, validate_event,
)


class EventDecodeError(ValueError):
    """Rejected malformed or unknown event, before subscriber dispatch."""


# Never import arbitrary event classes or deserialize arbitrary Python objects.
_KNOWN = {cls.event_name: cls for cls in (
    ResourceCreated, ResourceUpdated, ResourceDeleted, ActionExecuted, CollectionActionExecuted,
    LoginSucceeded, LoginFailed, LogoutSucceeded,
)}
_MAX_BYTES = 65536


def encode_event(event: AdminEvent) -> bytes:
    validate_event(event)
    payload = event.envelope()
    if event.type not in _KNOWN and not isinstance(event, CustomEvent):
        raise ValueError("Unregistered event type; use CustomEvent for named signals")
    raw = json.dumps({"version": 1, "event": payload}, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    if len(raw) > _MAX_BYTES:
        raise ValueError("Event exceeds the 64 KiB transport limit")
    return raw


def decode_event(raw: bytes) -> AdminEvent:
    if not isinstance(raw, bytes) or len(raw) > _MAX_BYTES:
        raise EventDecodeError("Invalid event payload size")
    try:
        envelope: Any = json.loads(raw)
        if not isinstance(envelope, dict) or set(envelope) != {"version", "event"} or envelope["version"] != 1:
            raise EventDecodeError("Unsupported event envelope version")
        payload = envelope["event"]
        if not isinstance(payload, dict) or not isinstance(payload.get("type"), str):
            raise EventDecodeError("Invalid event envelope")
        kind = payload["type"]
        model = _KNOWN.get(kind)
        if model is None:
            if not kind.startswith("custom."):
                raise EventDecodeError("Unknown event type")
            model = CustomEvent
        body = {key: value for key, value in payload.items() if key != "type"}
        if model is CustomEvent and body.get("name") != kind:
            raise EventDecodeError("Custom event name mismatch")
        event = model.model_validate(body)
        validate_event(event)
        return event
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, KeyError, ValueError) as error:
        raise EventDecodeError("Invalid or unsafe event payload") from error


class BrokerEventBus(InMemoryEventBus):
    """Shared matching/subscription API with explicit broker lifecycle.

    Producer publishes to broker; handlers run only on the consuming worker.
    On handler errors the broker must not acknowledge the event.
    """

    def __init__(self) -> None:
        super().__init__(on_error="log")
        self._started = False

    async def _dispatch(self, raw: bytes) -> DeliveryReport:
        event = decode_event(raw)
        return await self._deliver(event)

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def start(self) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError

    def _require_started(self) -> None:
        if not self._started:
            raise RuntimeError("Event bus is not started; call await bus.start()")
