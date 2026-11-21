"""Typed, metadata-only local events for Pyntral.

No ORM entities, submitted field values, authentication tokens or request bodies
are ever transported. Subscriber code is trusted application code; access to
records still requires an explicit, permission-checked lookup.
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from fnmatch import fnmatchcase
from typing import Any, Callable, ClassVar, Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field as PydanticField

from .logging import request_id_var


class FieldRef(BaseModel):
    """The *name* and schema kind of an affected field, never its value."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = PydanticField(min_length=1)
    kind: str = PydanticField(min_length=1)


class AdminEvent(BaseModel):
    """Immutable safe envelope. Subclasses only identify an event kind."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_name: ClassVar[str] = "admin.event"
    event_id: str = PydanticField(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = PydanticField(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    resource: str | None = None
    record_id: str | None = None
    actor_id: str | None = None
    fields: tuple[FieldRef, ...] = ()

    @property
    def type(self) -> str:
        return self.event_name

    def envelope(self) -> dict[str, Any]:
        """Portable JSON metadata for future broker adapters."""
        return {"type": self.type, **self.model_dump(mode="json")}


class ResourceEvent(AdminEvent):
    """Every resource mutation/action refers to a specific persisted row."""

    resource: str = PydanticField(min_length=1)
    record_id: str = PydanticField(min_length=1)


class ResourceCreated(ResourceEvent):
    event_name: ClassVar[str] = "resource.created"


class ResourceUpdated(ResourceEvent):
    event_name: ClassVar[str] = "resource.updated"


class ResourceDeleted(ResourceEvent):
    event_name: ClassVar[str] = "resource.deleted"


class ActionExecuted(ResourceEvent):
    event_name: ClassVar[str] = "action.executed"
    action: str


class CollectionActionExecuted(AdminEvent):
    """Resource/bulk action metadata. Does not disclose selected record IDs."""

    event_name: ClassVar[str] = "action.collection_executed"
    resource: str = PydanticField(min_length=1)
    action: str = PydanticField(min_length=1)
    action_kind: str = PydanticField(pattern=r"^(resource|bulk)$")


class LoginSucceeded(AdminEvent):
    event_name: ClassVar[str] = "auth.login_succeeded"


class LoginFailed(AdminEvent):
    event_name: ClassVar[str] = "auth.login_failed"


class LogoutSucceeded(AdminEvent):
    event_name: ClassVar[str] = "auth.logout"


class CustomEvent(AdminEvent):
    """A named business signal with identifiers and field kinds only."""

    event_name: ClassVar[str] = "custom.event"
    name: str = PydanticField(pattern=r"^[a-z][a-z0-9_.-]*$", min_length=1)

    @property
    def type(self) -> str:
        return self.name


EventHandler = Callable[[AdminEvent], Any]


@dataclass(frozen=True, slots=True)
class DeliveryReport:
    delivered: int
    failed: int


@dataclass(frozen=True, slots=True)
class Subscription:
    event_type: type[AdminEvent] | str
    handler: EventHandler
    resource: str | None


class InMemoryEventBus:
    """In-process ordered dispatcher; does not cross worker boundaries.

    Failure policy defaults to isolating subscriber errors: a successful DB
    commit cannot become an HTTP 500 because a notification handler failed.
    Handlers are awaited in registration order and must complete promptly.
    """

    def __init__(self, *, on_error: Literal["log", "raise"] = "log") -> None:
        if on_error not in ("log", "raise"):
            raise ValueError("on_error must be 'log' or 'raise'")
        self.on_error = on_error
        self._subscriptions: list[Subscription] = []
        self._logger = logging.getLogger("pyntral.events")

    async def start(self) -> None:
        """No external resources required."""

    async def close(self) -> None:
        """No external resources required."""

    def subscribe(
        self,
        event_type: type[AdminEvent] | str,
        handler: EventHandler,
        *,
        resource: str | None = None,
    ) -> Callable[[], None]:
        if not (isinstance(event_type, str) and event_type or
                isinstance(event_type, type) and issubclass(event_type, AdminEvent)):
            raise TypeError("event_type must be a nonempty event name/glob or AdminEvent class")
        if not callable(handler):
            raise TypeError("handler must be callable")
        if resource is not None and (not isinstance(resource, str) or not resource):
            raise ValueError("resource must be a nonempty string or None")
        subscription = Subscription(event_type, handler, resource)
        self._subscriptions.append(subscription)

        def unsubscribe() -> None:
            try:
                self._subscriptions.remove(subscription)
            except ValueError:
                pass

        return unsubscribe

    def on(self, event_type: type[AdminEvent] | str, *, resource: str | None = None):
        """Register a decorator-based callback: @admin.events.on(ResourceUpdated)."""
        def decorator(handler: EventHandler):
            self.subscribe(event_type, handler, resource=resource)
            return handler
        return decorator

    async def publish(self, event: AdminEvent) -> DeliveryReport:
        return await self._deliver(event)

    async def _deliver(self, event: AdminEvent) -> DeliveryReport:
        validate_event(event)
        delivered = failed = 0
        # Snapshot handles unsubscribe and new registrations during delivery.
        for subscription in tuple(self._subscriptions):
            kind = subscription.event_type
            matches = (isinstance(event, kind) if isinstance(kind, type)
                       else fnmatchcase(event.type, kind))
            if not matches or (subscription.resource is not None and not fnmatchcase(
                event.resource or "", subscription.resource
            )):
                continue
            try:
                response = subscription.handler(event)
                if inspect.isawaitable(response):
                    await response
                delivered += 1
            except Exception:
                failed += 1
                self._logger.exception(
                    "Subscriber failed for event=%s resource=%s event_id=%s",
                    event.type, event.resource, event.event_id,
                )
                if self.on_error == "raise":
                    raise
        return DeliveryReport(delivered=delivered, failed=failed)


def validate_event(event: AdminEvent) -> None:
    """Reject application-defined field values even for custom event subclasses."""
    if not isinstance(event, AdminEvent):
        raise TypeError("publish expects a metadata-only AdminEvent")
    allowed = {"type", "event_id", "occurred_at", "correlation_id", "resource",
               "record_id", "actor_id", "fields", "action", "name"}
    if set(event.envelope()) - allowed:
        raise ValueError("Events may contain identifiers and field metadata only")


def field_refs(adapter: Any, names: Any) -> tuple[FieldRef, ...]:
    """Resolve affected SQLAlchemy columns into metadata without fetching values."""
    from .orm import column_kind
    return tuple(FieldRef(name=name, kind=column_kind(adapter.columns[name]))
                 for name in sorted(set(names)) if name in adapter.columns)


def event_context() -> dict[str, str | None]:
    return {"correlation_id": request_id_var.get()}


class EventTransport(Protocol):
    """Structural contract for future cross-process transports."""

    def subscribe(self, event_type: type[AdminEvent] | str, handler: EventHandler,
                  *, resource: str | None = None) -> Callable[[], None]: ...

    def on(self, event_type: type[AdminEvent] | str, *, resource: str | None = None): ...

    async def publish(self, event: AdminEvent) -> DeliveryReport: ...

    async def start(self) -> None: ...

    async def close(self) -> None: ...


EventBus = InMemoryEventBus

__all__ = [
    "AdminEvent", "FieldRef", "ResourceCreated", "ResourceUpdated", "ResourceDeleted",
    "ActionExecuted", "CollectionActionExecuted", "LoginSucceeded", "LoginFailed", "LogoutSucceeded",
    "CustomEvent", "ResourceEvent", "InMemoryEventBus", "EventBus", "EventTransport", "DeliveryReport",
]
