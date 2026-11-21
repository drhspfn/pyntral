"""Serializable, permission-neutral layout directives for resource editors."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(slots=True)
class LayoutSection:
    """Group fields into an ordinary section, tab, or collapsible accordion.

    ``visible_if`` is UI-only presentation state, never an authorization rule.
    It accepts {"field": "active", "equals": True}.
    """

    id: str
    title: str
    fields: list[str] = field(default_factory=list)
    kind: Literal["section", "tab", "accordion"] = "section"
    visible_if: dict[str, Any] | None = None
    default_open: bool = True

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", self.id):
            raise ValueError("Layout section ID must be a lowercase slug")
        if not self.title.strip() or not self.fields or len(set(self.fields)) != len(self.fields):
            raise ValueError("Layout section must have a title and unique fields")
        if self.kind not in ("section", "tab", "accordion"):
            raise ValueError("Invalid layout section kind")
        if self.visible_if is not None and (
            set(self.visible_if) != {"field", "equals"} or
            not isinstance(self.visible_if.get("field"), str)
        ):
            raise ValueError("visible_if must have field and equals keys")
