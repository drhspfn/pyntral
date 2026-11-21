"""Explicit CRUD lifecycle hooks; no implicit authorization bypass."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(slots=True)
class OperationContext:
    """The validated operation environment for user-defined lifecycle hooks.

    ``payload`` is mutable during before-hooks. Added keys are revalidated
    against field-level authorization before a database write. After-hooks run
    after commit and must not be relied upon for durable event delivery.
    """

    operation: str
    resource: str
    principal: Any
    session: Any
    record: Any = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ResourceHook:
    before_create: Callable[[OperationContext], Any] | None = None
    after_create: Callable[[OperationContext], Any] | None = None
    before_update: Callable[[OperationContext], Any] | None = None
    after_update: Callable[[OperationContext], Any] | None = None
    before_delete: Callable[[OperationContext], Any] | None = None
    after_delete: Callable[[OperationContext], Any] | None = None
