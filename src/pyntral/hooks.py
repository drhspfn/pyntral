"""Explicit CRUD lifecycle hooks; no implicit authorization bypass."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(slots=True)
class OperationContext:
    """The validated operation environment for user-defined lifecycle hooks.

    Before-hooks receive raw input and may change ``payload``; added keys are
    revalidated against field-level authorization. For CRUD, the same context
    reaches the custom handler with converted values and the after-hook with
    the committed record. After-hooks run
    after commit and must not be relied upon for durable event delivery.
    """

    operation: str
    resource: str
    principal: Any
    session: Any
    record: Any = None
    payload: dict[str, Any] = field(default_factory=dict)
    action: str | None = None
    records: list[Any] | None = None  # Pre-authorized bulk records; never raw client IDs.


@dataclass(slots=True)
class ResourceHook:
    before_create: Callable[[OperationContext], Any] | None = None
    after_create: Callable[[OperationContext], Any] | None = None
    before_update: Callable[[OperationContext], Any] | None = None
    after_update: Callable[[OperationContext], Any] | None = None
    before_delete: Callable[[OperationContext], Any] | None = None
    after_delete: Callable[[OperationContext], Any] | None = None
    before_action: Callable[[OperationContext], Any] | None = None
    after_action: Callable[[OperationContext], Any] | None = None
