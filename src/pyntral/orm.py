"""SQLAlchemy adapter: typed schema, guarded CRUD, pagination and relation lookup."""

from __future__ import annotations

import datetime as dt
import decimal
import enum
import math
import uuid
from collections.abc import Mapping
from inspect import isawaitable
import re
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import String, and_, func, inspect, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.orm import RelationshipProperty, selectinload
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.sql.sqltypes import Numeric

from .filters import expression, supported_operators, validate_filters
from .orm_types import type_name


from .auth import Principal, maybe_await
from .resources import Resource

PRIVATE_NAMES = ("password", "secret", "token", "api_key", "private_key", "credential")


class AdminError(Exception):
    def __init__(self, status: int, message: str, code: str = "error", details: Any = None):
        self.status = status
        self.message = message
        self.code = code
        self.details = details
        super().__init__(message)


def column_kind(column: Any) -> str:
    """Backward-compatible alias for SQLAlchemy type classification."""
    return type_name(column)


def convert_value(column: Any, value: Any) -> Any:
    if value is None:
        return None
    kind = column_kind(column)
    try:
        if kind == "integer":
            if isinstance(value, bool):
                raise ValueError("expected integer")
            return int(value)
        if kind == "number":
            number = decimal.Decimal(str(value)) if isinstance(column.type, Numeric) else float(value)
            finite = number.is_finite() if isinstance(number, decimal.Decimal) else math.isfinite(number)
            if not finite:
                raise ValueError("number must be finite")
            return number
        if kind == "boolean":
            if isinstance(value, bool):
                return value
            if str(value).lower() in ("true", "1"):
                return True
            if str(value).lower() in ("false", "0"):
                return False
            raise ValueError("expected boolean")
        if kind == "uuid":
            return uuid.UUID(str(value))
        if kind == "datetime":
            result = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if column.type.timezone and result.tzinfo is None:
                raise ValueError("timezone required")
            return result
        if kind == "date":
            return dt.date.fromisoformat(str(value))
        if kind == "time":
            return dt.time.fromisoformat(str(value))
        if kind == "enum":
            if isinstance(value, enum.Enum):
                return value
            value = str(value)
            if value not in list(column.type.enums):
                raise ValueError("invalid enum option")
            return value
        if kind in ("json", "array"):
            if kind == "array" and not isinstance(value, list):
                raise ValueError("expected array")
            if kind == "json" and not isinstance(value, (list, dict)):
                raise ValueError("expected JSON object or array")
            return value
        if kind == "binary":
            raise ValueError("binary fields cannot be edited")
        if not isinstance(value, str):
            raise ValueError("expected string")
        return value
    except (ValueError, OverflowError, TypeError, decimal.InvalidOperation) as exc:
        raise AdminError(422, f"Invalid value for {column.key}: {exc}", "validation_error") from exc


class MapperAdapter:
    def __init__(self, resource: Resource):
        self.resource = resource
        if not resource.name or re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]*", resource.name) is None:
            raise ValueError("Resource name must be a URL-safe slug")
        self.mapper = inspect(resource.model)
        self.columns = {prop.key: prop.columns[0] for prop in self.mapper.column_attrs}
        keys = list(self.mapper.primary_key)
        if len(keys) != 1:
            raise ValueError(f"{resource.model.__name__}: exactly one primary key required")
        self.pk = keys[0]
        self.pk_name = next((k for k, c in self.columns.items() if c is self.pk), self.pk.key)
        if resource.version_field is not None:
            col = self.columns.get(resource.version_field)
            if col is None or column_kind(col) != "integer" or self.mapper.version_id_col is not col:
                raise ValueError("version_field must be an integer SQLAlchemy version_id_col")
        self.relations: dict[str, RelationshipProperty] = {
            prop.key: prop for prop in self.mapper.relationships
        }
        self.foreign_key_fields = {
            name for name, column in self.columns.items()
            if any(prop.direction.name == "MANYTOONE" and column in prop.local_columns
                   for prop in self.relations.values())
        }
        for field_name in set(resource._server_defaults) | set(resource._server_onupdate):
            if field_name not in self.columns:
                raise ValueError(f"Server-managed field is not mapped: {field_name}")
        for name, virtual in resource.virtual_fields.items():
            if name in self.columns or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]*", name):
                raise ValueError(f"Invalid or conflicting virtual field: {name}")
        for mode, sections in (("form", resource.form_sections), ("detail", resource.detail_sections)):
            if len({sec.id for sec in sections}) != len(sections):
                raise ValueError(f"Duplicate {mode} layout section IDs")
            seen_fields: set[str] = set()
            for section in sections:
                if seen_fields.intersection(section.fields):
                    raise ValueError(f"Duplicate field in {mode} layout sections")
                seen_fields.update(section.fields)
                for name in section.fields:
                    if name not in self.columns and name not in resource.virtual_fields:
                        raise ValueError(f"Unknown {mode} layout field: {name}")
                if section.visible_if and section.visible_if["field"] not in self.columns and section.visible_if["field"] not in resource.virtual_fields:
                    raise ValueError(f"Unknown conditional layout field: {section.visible_if['field']}")
        for name, configuration in resource.fields.items():
            if name not in self.columns:
                raise ValueError(f"Unknown column in {resource.name}: {name}")
            if configuration.filter_operators is not None:
                supported = self.filter_operators(name, ignore_custom=True)
                if any(operator not in supported for operator in configuration.filter_operators):
                    raise ValueError(f"Unsupported filter operator for {resource.name}.{name}")
            if configuration.filter and configuration.filter.operators is not None:
                supported = self.filter_operators(name, ignore_custom=True)
                if any(operator not in supported for operator in configuration.filter.operators):
                    raise ValueError(f"Unsupported filter operator for {resource.name}.{name}")
        for name in (resource.list_fields or []) + resource.search_fields:
            if name not in self.columns and not (name in resource.virtual_fields and name not in resource.search_fields):
                raise ValueError(f"Unknown column in {resource.name}: {name}")
        for name in resource.search_fields:
            if not self.visible(name):
                raise ValueError(f"Cannot search a hidden field: {name}")
            if column_kind(self.columns[name]) not in ("string", "enum"):
                raise ValueError(f"Search field {name} must be text/enum")
        if resource.title_field and (
            resource.title_field not in self.columns or not self.visible(resource.title_field)
        ):
            raise ValueError("title_field must be a visible mapped column")
        if resource.visible_name is not None:
            attribute = resource.visible_name
            name = getattr(attribute, "key", None)
            if not isinstance(attribute, InstrumentedAttribute) or name not in self.columns or (
                getattr(resource.model, name) is not attribute
            ) or not self.visible(name):
                raise ValueError("visible_name must refer to a visible mapped column on this model")
            if column_kind(self.columns[name]) not in ("string", "integer", "uuid", "enum"):
                raise ValueError("visible_name must be a text, integer, UUID or enum column")
            if resource.title_field and resource.title_field != name:
                raise ValueError("Specify either title_field or visible_name, not conflicting values")
        if resource.label_factory is not None and not callable(resource.label_factory):
            raise ValueError("label_factory must be callable")
        for name in resource.relationships:
            if name not in self.relations:
                raise ValueError(f"Unknown relationship on {resource.name}: {name}")
        if len({a.name for a in resource.actions}) != len(resource.actions):
            raise ValueError("Action names must be unique")
        if any(re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]*", a.name) is None
               for a in resource.actions):
            raise ValueError("Action names must be URL-safe slugs")

    def _field(self, name: str) -> Any:
        return self.resource.fields.get(name)

    def filter_operators(self, name: str, *, ignore_custom: bool = False) -> tuple[str, ...]:
        base = (("eq", "neq") if name in self.foreign_key_fields else
                supported_operators(column_kind(self.columns[name])))
        config = self._field(name)
        if not ignore_custom and config:
            if config.filter and config.filter.operators is not None:
                return tuple(config.filter.operators)
            if config.filter_operators is not None:
                return tuple(config.filter_operators)
        return base

    def visible(self, name: str) -> bool:
        opt = self._field(name)
        return (opt is None or opt.visible) and not (
            opt is None and any(secret in name.lower() for secret in PRIVATE_NAMES)
        )

    def view_config(self, name: str, view: str) -> Any:
        opt = self._field(name)
        return getattr(opt, view, None) if opt else None

    def view_visible(self, name: str, view: str) -> bool:
        if not self.visible(name):
            return False
        override = self.view_config(name, view)
        return override is None or override.visible is not False

    def writable(self, name: str) -> bool:
        col = self.columns[name]
        opt = self._field(name)
        return self.visible(name) and name != self.pk_name and not (opt and opt.readonly) and (
            not col.computed and not col.identity and column_kind(col) != "binary"
        )

    def serialize(self, record: Any, allowed_fields: set[str] | None = None) -> dict[str, Any]:
        values = {name: getattr(record, name) for name in self.columns
                  if self.visible(name) and (allowed_fields is None or name in allowed_fields)}
        for name, virtual in self.resource.virtual_fields.items():
            if virtual.getter is not None and (allowed_fields is None or name in allowed_fields):
                value = virtual.getter(record)
                if isawaitable(value):
                    raise AdminError(500, "Virtual field getter must be synchronous", "virtual_field_error")
                values[name] = value
        return jsonable_encoder(values)

    def pk_value(self, raw: str) -> Any:
        return convert_value(self.pk, raw)

    def _related_resource(self, relationship: RelationshipProperty, registry: dict[str, Any]) -> str | None:
        target = relationship.mapper.class_
        return next((name for name, adapter in registry.items() if adapter.resource.model is target), None)

    def metadata(self, registry: dict[str, Any]) -> dict[str, Any]:
        fields = []
        for name, column in self.columns.items():
            if not self.visible(name):
                continue
            options = self._field(name)
            kind = column_kind(column)
            relation = next(
                (
                    {"resource": self._related_resource(prop, registry), "field": prop.key}
                    for prop in self.relations.values()
                    if prop.direction.name == "MANYTOONE"
                    and any(column is local for local in prop.local_columns)
                ),
                None,
            )
            is_required = (
                not column.nullable
                and column.default is None
                and column.server_default is None
                and not column.primary_key
                and not column.identity
            )
            view_configs = {}
            for view in ("list", "create", "edit", "show", "filter"):
                cfg = self.view_config(name, view)
                view_configs[view] = {
                    "visible": self.view_visible(name, view),
                    "readonly": (cfg.readonly if cfg and cfg.readonly is not None else not self.writable(name)),
                    "required": (cfg.required if cfg and cfg.required is not None else
                                 options.required if options and options.required is not None else is_required),
                    "component": (cfg.component if cfg and cfg.component is not None else
                                  options.components.get(view) if options else None),
                    "order": cfg.order if cfg else None,
                }
            fields.append(
                {
                    "name": name,
                    "label": options.label if options and options.label else name.replace("_", " ").title(),
                    "kind": kind,
                    "required": options.required if options and options.required is not None else is_required,
                    "readonly": not self.writable(name),
                    "primaryKey": name == self.pk_name,
                    "nullable": column.nullable,
                    "widget": options.widget if options else None,
                    "help": options.help if options else None,
                    "maxLength": getattr(column.type, "length", None) if kind == "string" else None,
                    "precision": getattr(column.type, "precision", None) if kind == "number" else None,
                    "scale": getattr(column.type, "scale", None) if kind == "number" else None,
                    "filterWidth": options.filter_width if options else None,
                    "filterOperators": list(self.filter_operators(name)),
                    "options": (
                        options.options if options and options.options is not None
                        else list(column.type.enums) if kind == "enum" else None
                    ),
                    "relation": relation if relation and relation["resource"] else None,
                    "components": options.components if options else {},
                    "span": options.span if options else 1,
                    "views": view_configs,
                }
            )
        for name, virtual in self.resource.virtual_fields.items():
            # Each access is independently checked by the backend; a setter-only
            # field must never be serialized into a list or record response.
            views = {mode: {
                "visible": virtual.getter is not None if mode in ("list", "show", "filter")
                else virtual.setter is not None,
                "readonly": virtual.setter is None,
                "required": virtual.required if mode == "create" else False,
                "component": virtual.component,
                "order": None,
            } for mode in ("list", "create", "edit", "show", "filter")}
            views["filter"]["visible"] = False  # Not backed by an SQL expression.
            fields.append({
                "name": name, "label": virtual.label or name.replace("_", " ").title(),
                "kind": virtual.kind, "required": virtual.required, "readonly": virtual.setter is None,
                "primaryKey": False, "nullable": True, "widget": None, "help": None,
                "maxLength": None, "precision": None, "scale": None, "filterWidth": None,
                "filterOperators": [], "options": None, "relation": None,
                "components": {}, "span": 1, "views": views,
            })
        return {
            "id": self.resource.name,
            "label": self.resource.label,
            "icon": self.resource.icon,
            "navigation": self.resource.navigation,
            "navigationOrder": self.resource.navigation_order,
            "primaryKey": self.pk_name,
            "versionField": self.resource.version_field,
            "titleField": self._title_field(),
            "layouts": {mode: [
                {"id": section.id, "title": section.title, "kind": section.kind,
                 "fields": section.fields, "visibleIf": section.visible_if,
                 "defaultOpen": section.default_open}
                for section in items
            ] for mode, items in (("form", self.resource.form_sections),
                                  ("detail", self.resource.detail_sections))},
            "formLayout": self.resource.form_layout,
            "detailLayout": self.resource.detail_layout,
            "pageSize": self.resource.page_size,
            "showSearch": self.resource.show_search,
            "crudViews": self.resource.crud_views,
            "fields": fields,
            "listFields": [
                name for name in (self.resource.list_fields or list(self.columns)[:6])
                if (self.view_visible(name, "list") if name in self.columns
                    else self.resource.virtual_fields[name].getter is not None)
            ],
            "searchFields": self.resource.search_fields,
            "relationships": [
                {
                    "name": name,
                    "resource": self._related_resource(prop, registry),
                    "many": prop.uselist,
                    "label": (self.resource.relationships[name].label or name.replace("_", " ").title())
                    if name in self.resource.relationships else name.replace("_", " ").title(),
                    "selectable": self.resource.relationships[name].selectable
                    if name in self.resource.relationships else False,
                    "layout": self.resource.relationships[name].layout
                    if name in self.resource.relationships else "table",
                    **({"editable": True} if prop.uselist and prop.secondary is not None and
                        not prop.viewonly else {}),
                }
                for name, prop in self.relations.items()
                if self._related_resource(prop, registry) is not None
                and (name not in self.resource.relationships or self.resource.relationships[name].visible)
            ],
            "actions": [
                {"name": a.name, "label": a.label or a.name.replace("_", " ").title(),
                 "variant": a.variant, "confirmation": a.confirmation,
                 "position": a.position, "appearance": a.appearance,
                 "component": a.component, "dialog": a.dialog, "icon": a.icon, "kind": a.kind}
                for a in self.resource.actions
            ],
            "capabilities": {
                "create": self.resource.allow_create,
                "edit": self.resource.allow_edit,
                "delete": self.resource.allow_delete,
                "show": self.resource.allow_show,
            },
        }

    def _title_field(self) -> str:
        if self.resource.visible_name is not None:
            return self.resource.visible_name.key
        return self.resource.title_field or self._guess_title()

    def _label(self, row: Any) -> str:
        if self.resource.label_factory is not None:
            label = self.resource.label_factory(row)
            if not isinstance(label, str):
                raise AdminError(500, "label_factory must return a string", "invalid_label")
            return label
        return str(getattr(row, self._title_field()))

    def _guess_title(self) -> str:
        for name in ("name", "title", "email", "username", self.pk_name):
            if name in self.columns and self.visible(name):
                return name
        return self.pk_name

    def parsed_payload(self, payload: Mapping[str, Any], *, create: bool) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise AdminError(422, "Expected JSON object", "validation_error")
        unexpected = set(payload) - set(self.columns) - set(self.resource.virtual_fields)
        forbidden = [name for name in payload if name in self.columns and not self.writable(name)]
        if unexpected or forbidden:
            raise AdminError(422, "Unknown or read-only fields", "validation_error", {
                "fields": sorted(unexpected | set(forbidden))
            })
        out = {}
        for name, value in payload.items():
            if name in self.resource.virtual_fields:
                virtual = self.resource.virtual_fields[name]
                if virtual.setter is None:
                    raise AdminError(422, "Read-only virtual field", "validation_error")
                if virtual.required and create and value in (None, ""):
                    raise AdminError(422, f"{name} is required", "validation_error")
                out[name] = value
                continue
            view = self.view_config(name, "create" if create else "edit")
            if view and view.required and (value is None or value == ""):
                raise AdminError(422, f"{name} is required", "validation_error")
            col = self.columns[name]
            if value is None and not col.nullable:
                raise AdminError(422, f"{name} cannot be null", "validation_error")
            out[name] = convert_value(col, value)
        if create:
            missing_virtual = [name for name, field in self.resource.virtual_fields.items()
                               if field.required and field.setter is not None and name not in out]
            if missing_virtual:
                raise AdminError(422, "Missing required virtual fields", "validation_error",
                                 {"fields": missing_virtual})
            missing = [
                name for name, col in self.columns.items()
                if self.writable(name) and not col.nullable and col.default is None
                and col.server_default is None and name not in out
            ]
            missing.extend(
                name for name in self.columns if name not in out and
                self.view_visible(name, "create") and
                (override := self.view_config(name, "create")) is not None and
                override.required is True and name not in missing
            )
            if missing:
                raise AdminError(422, "Missing required fields", "validation_error", {"fields": missing})
        return out

    async def _scope(self, statement: Any, principal: Principal) -> Any:
        if self.resource.scope:
            return await maybe_await(self.resource.scope(principal, statement))
        return statement

    async def list(
        self, session: Any, principal: Principal, *, offset: int = 0,
        limit: int | None = None, q: str = "", sort: str | None = None,
        desc: bool = False, filters: dict[str, str] | None = None,
        allowed_fields: set[str] | None = None,
        filter_fields: set[str] | None = None,
    ) -> dict[str, Any]:
        if offset < 0:
            raise AdminError(422, "offset must be nonnegative")
        limit = min(max(limit or self.resource.page_size, 1), 200)
        stmt = select(self.resource.model)
        searchable = [n for n in self.resource.search_fields if allowed_fields is None or n in allowed_fields]
        if q and searchable:
            stmt = stmt.where(or_(*(
                func.lower(getattr(self.resource.model, n)).like(f"%{q.lower().replace('%', r'\%').replace('_', r'\_')}%", escape="\\")
                for n in searchable
            )))
        exposed = {name for name in self.columns if self.view_visible(name, "filter") and
                   (filter_fields is None or name in filter_fields)}
        overrides = {name: self.filter_operators(name) for name in self.columns}
        clauses = validate_filters(filters or {}, self.columns, exposed, overrides)
        for name, operator, raw in clauses:
            stmt = stmt.where(expression(self.columns[name], getattr(self.resource.model, name),
                                         operator, raw, convert_value))
        stmt = await self._scope(stmt, principal)
        # The same scoped filter is used for both count and rows.
        total_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = (await maybe_await(session.execute(total_stmt))).scalar_one()
        if sort:
            if sort not in self.columns or not self.visible(sort) or (allowed_fields is not None and sort not in allowed_fields):
                raise AdminError(422, "Invalid sort column")
            key = getattr(self.resource.model, sort)
        else:
            key = getattr(self.resource.model, self.pk_name)
        stmt = stmt.order_by(key.desc() if desc else key.asc()).limit(limit).offset(offset)
        result = await maybe_await(session.execute(stmt))
        return {"items": [self.serialize(row, allowed_fields) for row in result.scalars().all()],
                "total": total, "offset": offset, "limit": limit}

    async def get(self, session: Any, identifier: str, principal: Principal) -> Any:
        stmt = await self._scope(
            select(self.resource.model).where(getattr(self.resource.model, self.pk_name) == self.pk_value(identifier)),
            principal,
        )
        result = await maybe_await(session.execute(stmt))
        record = result.scalar_one_or_none()
        if record is None:
            raise AdminError(404, "Record not found", "not_found")
        return record

    async def create(self, session: Any, payload: dict[str, Any]) -> dict[str, Any]:
        parsed = self.parsed_payload(payload, create=True)
        mapped = {key: value for key, value in parsed.items() if key in self.columns}
        for key, factory in self.resource._server_defaults.items():
            mapped[key] = factory()
        record = self.resource.model(**mapped)
        for key, value in parsed.items():
            if key in self.resource.virtual_fields:
                await maybe_await(self.resource.virtual_fields[key].setter(record, value))
        session.add(record)
        await self._commit(session)
        await maybe_await(session.refresh(record))
        return self.serialize(record)

    async def update(self, session: Any, record: Any, payload: dict[str, Any]) -> dict[str, Any]:
        for name, value in self.parsed_payload(payload, create=False).items():
            if name in self.resource.virtual_fields:
                await maybe_await(self.resource.virtual_fields[name].setter(record, value))
            else:
                setattr(record, name, value)
        for key, factory in self.resource._server_onupdate.items():
            setattr(record, key, factory())
        await self._commit(session)
        await maybe_await(session.refresh(record))
        return self.serialize(record)

    async def delete(self, session: Any, record: Any) -> None:
        await maybe_await(session.delete(record))
        await self._commit(session)

    async def _commit(self, session: Any) -> None:
        try:
            await maybe_await(session.commit())
        except StaleDataError as exc:
            await maybe_await(session.rollback())
            raise AdminError(409, "Record was modified concurrently", "concurrent_update") from exc
        except IntegrityError as exc:
            await maybe_await(session.rollback())
            raise AdminError(409, "Database constraint prevents this operation. The record may be referenced by other records or a value must be unique.", "integrity_error") from exc
        except SQLAlchemyError:
            await maybe_await(session.rollback())
            raise

    async def options(
        self, session: Any, principal: Principal, query: str = "", limit: int = 30,
        ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        if len(query) > 200:
            raise AdminError(422, "Search text too long", "validation_error")
        title = self._title_field()
        stmt = select(self.resource.model)
        if ids:
            if len(ids) > 100:
                raise AdminError(422, "Too many selected IDs", "validation_error")
            keys = [self.pk_value(v) for v in ids]
            stmt = stmt.where(getattr(self.resource.model, self.pk_name).in_(keys))
        elif query:
            columns = [n for n in (self.resource.search_fields or [title])
                       if n in self.columns and column_kind(self.columns[n]) in ("string", "enum")]
            if columns:
                # Escape LIKE wildcards: search is literal and cannot broaden a scope.
                escaped = query.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                stmt = stmt.where(or_(*(func.lower(getattr(self.resource.model, n)).like(
                    f"%{escaped}%", escape="\\") for n in columns)))
            elif title == self.pk_name:
                try:
                    stmt = stmt.where(getattr(self.resource.model, self.pk_name) == self.pk_value(query))
                except AdminError:
                    return []
        stmt = (await self._scope(stmt, principal)).order_by(
            getattr(self.resource.model, self.pk_name)
        ).limit(min(limit, 100))
        result = await maybe_await(session.execute(stmt))
        return [
            {"value": jsonable_encoder(getattr(row, self.pk_name)), "label": self._label(row)}
            for row in result.scalars()
        ]

    async def relation(
        self, session: Any, principal: Principal, record: Any, name: str,
        target: "MapperAdapter", offset: int = 0, limit: int = 20, query: str = "",
        allowed_fields: set[str] | None = None,
    ) -> dict[str, Any]:
        if name not in self.relations:
            raise AdminError(404, "Relationship not found", "not_found")
        prop = self.relations[name]
        if prop.mapper.class_ is not target.resource.model:
            raise AdminError(404, "Relationship is not registered", "not_found")
        # Build a DB-backed relationship query using SQLAlchemy's with_parent.
        from sqlalchemy.orm import with_parent
        stmt = await target._scope(
            select(target.resource.model).where(with_parent(record, getattr(self.resource.model, name))),
            principal,
        )
        if len(query) > 200:
            raise AdminError(422, "Search text too long", "validation_error")
        if query:
            searchable = [n for n in (target.resource.search_fields or [target._title_field()])
                          if n in target.columns and column_kind(target.columns[n]) in ("string", "enum")
                          and (allowed_fields is None or n in allowed_fields)]
            if searchable:
                escaped = query.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                stmt = stmt.where(or_(*(func.lower(getattr(target.resource.model, n)).like(
                    f"%{escaped}%", escape="\\") for n in searchable)))
            elif target._title_field() == target.pk_name:
                try:
                    stmt = stmt.where(getattr(target.resource.model, target.pk_name) == target.pk_value(query))
                except AdminError:
                    return {"items": [], "total": 0, "offset": offset, "limit": limit}
        count = (await maybe_await(session.execute(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        ))).scalar_one()
        results = await maybe_await(session.execute(
            stmt.order_by(getattr(target.resource.model, target.pk_name)).offset(offset).limit(min(limit, 100))
        ))
        return {"items": [target.serialize(row, allowed_fields) for row in results.scalars()],
                "total": count, "offset": offset, "limit": limit}
