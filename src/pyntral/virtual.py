"""Explicitly declared virtual fields; no SQL query or implicit model exposure."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(slots=True)
class VirtualField:
    """A computed and/or write-only resource field.

    Read handlers are synchronous pure functions of a mapped record. Write
    handlers may be sync/async and receive (record, validated_value); they run
    inside the ORM transaction and must not commit it themselves.
    """

    kind: str = "string"
    label: str | None = None
    getter: Callable[[Any], Any] | None = None
    setter: Callable[[Any, Any], Any] | None = None
    read_role: str | None = None
    write_role: str | None = None
    required: bool = False
    component: str | None = None
    widget: str | None = None

    def __post_init__(self) -> None:
        if self.getter is None and self.setter is None:
            raise ValueError("VirtualField requires a getter or setter")
        if self.kind not in ("string", "integer", "number", "boolean", "date", "datetime", "json", "uuid"):
            raise ValueError("Unsupported virtual field kind")
