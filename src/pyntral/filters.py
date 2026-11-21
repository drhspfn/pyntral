"""Filter expressions shared by the SQLAlchemy adapter and metadata-driven UI.

Public HTTP contract:
  filter.name.contains=abc
  filter.amount.between={"from":10,"to":20}
  filter.status.in=["pending","fulfilled"]
  filter.status.not_in=["cancelled"]
The shorthand filter.name=value means equality.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy import func

from .orm_types import type_name  # column-kind helper with no adapter dependency

FILTER_OPERATORS: dict[str, tuple[str, ...]] = {
    "string": ("eq", "neq", "contains", "starts_with", "ends_with"),
    "uuid": ("eq", "neq"),
    "integer": ("eq", "neq", "gt", "gte", "lt", "lte", "between"),
    "number": ("eq", "neq", "gt", "gte", "lt", "lte", "between"),
    "date": ("eq", "neq", "gt", "gte", "lt", "lte", "between"),
    "datetime": ("eq", "neq", "gt", "gte", "lt", "lte", "between"),
    "time": ("eq", "neq", "gt", "gte", "lt", "lte", "between"),
    "boolean": ("eq",),
    "enum": ("eq", "neq", "in", "not_in"),
    "json": (), "array": (), "binary": (),
}


def supported_operators(kind: str) -> tuple[str, ...]:
    return FILTER_OPERATORS.get(kind, ())


def parse_filter_key(raw: str) -> tuple[str, str]:
    """Return field and operator; accept a field-only equality shorthand."""
    name, sep, operator = raw.partition(".")
    if not name or (sep and (not operator or "." in operator)):
        raise ValueError("Invalid filter key")
    return name, operator if sep else "eq"


def expression(column: Any, attribute: Any, operator: str, raw: str, convert: Any) -> Any:
    """Build a bound SQLAlchemy expression; never interpolate user input into SQL."""
    from .orm import AdminError  # lazy to keep metadata imports independent

    kind = type_name(column)
    if operator not in supported_operators(kind):
        raise AdminError(422, f"Unsupported {operator} filter for {column.key}", "invalid_filter")
    if len(raw) > 4096:
        raise AdminError(422, "Filter value is too long", "invalid_filter")
    if operator in ("in", "not_in"):
        try:
            values = json.loads(raw)
        except (ValueError, TypeError):
            values = None
        if not isinstance(values, list) or not 1 <= len(values) <= 100:
            raise AdminError(422, "Include/Exclude expects 1–100 values", "invalid_filter")
        if any(isinstance(v, (dict, list)) for v in values):
            raise AdminError(422, "Include/Exclude expects scalar values", "invalid_filter")
        typed = [convert(column, value) for value in values]
        return attribute.in_(typed) if operator == "in" else attribute.not_in(typed)
    if operator == "between":
        try:
            bounds = json.loads(raw)
        except (ValueError, TypeError):
            bounds = None
        if not isinstance(bounds, dict) or set(bounds) != {"from", "to"}:
            raise AdminError(422, "Between requires from and to", "invalid_filter")
        start = convert(column, bounds["from"])
        end = convert(column, bounds["to"])
        try:
            invalid = start is None or end is None or start > end
        except TypeError:
            invalid = True
        if invalid:
            raise AdminError(422, "Between bounds are invalid or reversed", "invalid_filter")
        return attribute.between(start, end)
    typed = convert(column, raw)
    if operator == "eq":
        return attribute == typed
    if operator == "neq":
        return attribute != typed
    if operator == "gt":
        return attribute > typed
    if operator == "gte":
        return attribute >= typed
    if operator == "lt":
        return attribute < typed
    if operator == "lte":
        return attribute <= typed
    if operator in ("contains", "starts_with", "ends_with"):
        # Always treat wildcard input literally. SQLAlchemy binds the resulting string.
        literal = typed.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = {"contains": f"%{literal}%", "starts_with": f"{literal}%", "ends_with": f"%{literal}"}[operator]
        return func.lower(attribute).like(pattern, escape="\\")
    raise AdminError(422, "Invalid filter operator", "invalid_filter")


def validate_filters(filters: Mapping[str, str], columns: Mapping[str, Any], allowed: set[str],
                     overrides: Mapping[str, tuple[str, ...]]) -> list[tuple[str, str, str]]:
    """Validate the complete request before building SQL, including duplicate clauses."""
    from .orm import AdminError

    if len(filters) > 80:
        raise AdminError(422, "Too many filters", "invalid_filter")
    clauses: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for key, value in filters.items():
        try:
            field, operator = parse_filter_key(key)
        except ValueError as exc:
            raise AdminError(422, str(exc), "invalid_filter") from exc
        if field not in columns or field not in allowed:
            raise AdminError(422, f"Unknown filter field: {field}", "invalid_filter")
        enabled = overrides.get(field, supported_operators(type_name(columns[field])))
        if operator not in enabled:
            raise AdminError(422, f"Unsupported {operator} filter for {field}", "invalid_filter")
        if (field, operator) in seen:
            raise AdminError(422, "Duplicate filter", "invalid_filter")
        seen.add((field, operator))
        clauses.append((field, operator, value))
    # Enum Include and Exclude are mutually exclusive by design.
    # Frontend moves a value from one set to the other; malformed HTTP clients
    # must not silently submit contradictory selection filters.
    for field in {name for name, _, _ in clauses}:
        by_operator = {operator: value for name, operator, value in clauses if name == field}
        if "in" in by_operator and "not_in" in by_operator:
            try:
                included = json.loads(by_operator["in"])
                excluded = json.loads(by_operator["not_in"])
                if isinstance(included, list) and isinstance(excluded, list) and any(
                    item in excluded for item in included
                ):
                    raise AdminError(422, "Include and Exclude must not overlap", "invalid_filter")
            except (ValueError, TypeError):
                # Invalid JSON is diagnosed by expression() with a typed error.
                pass
    return clauses
