"""SQLAlchemy adapter: typed schema, guarded CRUD, pagination and relation lookup."""

from __future__ import annotations

import base64
import binascii
import json
import datetime as dt
import decimal
import enum
import math
import uuid
from collections.abc import Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from inspect import isawaitable
import re
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import String, and_, event, func, inspect, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.orm import RelationshipProperty, selectinload
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.sql.sqltypes import Numeric

from .filters import expression, supported_operators, validate_filters
from .orm_types import type_name


from .auth import Principal, maybe_await
from .resources import Resource
from .hooks import OperationContext
from .sidebar import icon_metadata

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
        if not keys:
            raise ValueError(f"{resource.model.__name__}: primary key required")
        self.pk = keys[0]
        self.pk_names = tuple(next((k for k, c in self.columns.items() if c is key), key.key) for key in keys)
        self.pk_name = self.pk_names[0]
        self.composite = len(keys) > 1
        self.identity_field = "__pyntral_id" if self.composite else self.pk_name
        if self.composite:
            if self.identity_field in self.columns or self.identity_field in resource.virtual_fields:
                raise ValueError("Reserved composite identity field: __pyntral_id")
            if any(column_kind(key) not in ("integer", "string", "uuid") for key in keys):
                raise ValueError("Composite primary key components must be integer, string or UUID")

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
            if configuration.file_upload is not None and column_kind(self.columns[name]) != "json":
                raise ValueError(f"File upload mock field must use JSON column: {resource.name}.{name}")
            if configuration.dependency is not None:
                source = configuration.dependency.source
                if source == name or source not in self.columns or not self.visible(source):
                    raise ValueError(f"Invalid dependency source for {resource.name}.{name}: {source}")
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

    def writable(self, name: str, *, create: bool = False) -> bool:
        col = self.columns[name]
        opt = self._field(name)
        if name in self.pk_names:
            if not (self.composite and create) or col.autoincrement is True:
                return False
        return self.visible(name) and name != self.resource.version_field and not (opt and opt.readonly) and (
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
        if self.composite and all(name in values for name in self.pk_names):
            values[self.identity_field] = self.record_identifier(record)
        return jsonable_encoder(values)

    def identity_values(self, record: Any) -> tuple[Any, ...]:
        return tuple(getattr(record, name) for name in self.pk_names)

    def encode_identity(self, values: tuple[Any, ...]) -> str:
        if not self.composite:
            return str(values[0])
        data = json.dumps([str(value) for value in values], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        identifier = base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")
        if len(identifier) > 8192:
            raise AdminError(422, "Composite record identifier is too long", "validation_error")
        return identifier

    def record_identifier(self, record: Any) -> str:
        return self.encode_identity(self.identity_values(record))

    def persisted_identifier(self, record: Any, max_length: int) -> str:
        identifier = self.record_identifier(record)
        if len(identifier) > max_length:
            raise AdminError(422, "Record identifier exceeds the configured feature storage limit", "validation_error")
        return identifier

    def pk_value(self, raw: str) -> Any:
        if not self.composite:
            return convert_value(self.pk, raw)
        try:
            if len(raw) > 8192 or re.fullmatch(r"[A-Za-z0-9_-]+", raw) is None:
                raise ValueError("invalid identifier")
            parts = json.loads(base64.b64decode(raw + "=" * (-len(raw) % 4), altchars=b"-_", validate=True))
            if not isinstance(parts, list) or len(parts) != len(self.pk_names) or any(not isinstance(p, str) for p in parts):
                raise ValueError("invalid key components")
            values = tuple(convert_value(self.columns[name], part) for name, part in zip(self.pk_names, parts))
            if self.encode_identity(values) != raw:
                raise ValueError("noncanonical identifier")
            return values
        except (ValueError, UnicodeError, binascii.Error, AdminError) as exc:
            raise AdminError(422, "Invalid composite record identifier", "validation_error") from exc

    def identity_predicate(self, identifier: str) -> Any:
        value = self.pk_value(identifier)
        if not self.composite:
            return getattr(self.resource.model, self.pk_name) == value
        return and_(*(getattr(self.resource.model, name) == part for name, part in zip(self.pk_names, value)))

    def identities_predicate(self, identifiers: list[str]) -> Any:
        if not self.composite:
            return getattr(self.resource.model, self.pk_name).in_([self.pk_value(value) for value in identifiers])
        return or_(*(self.identity_predicate(value) for value in identifiers)) if identifiers else False

    def identity_order(self) -> list[Any]:
        return [getattr(self.resource.model, name) for name in self.pk_names]

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
                    and len(prop.local_columns) == 1 and len(prop.mapper.primary_key) == 1
                    and any(remote is prop.mapper.primary_key[0] for _, remote in prop.local_remote_pairs)
                    and any(column is local for local in prop.local_columns)
                ),
                None,
            )
            is_required = (
                not column.nullable
                and column.default is None
                and column.server_default is None
                and (not column.primary_key or self.writable(name, create=True))
                and not column.identity
            )
            writable = self.writable(name) or self.writable(name, create=True)
            view_configs = {}
            for view in ("list", "create", "edit", "show", "filter"):
                cfg = self.view_config(name, view)
                view_configs[view] = {
                    "visible": self.view_visible(name, view),
                    "readonly": not self.writable(name, create=view == "create") or (cfg is not None and cfg.readonly is True),
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
                    "readonly": not writable,
                    "primaryKey": name in self.pk_names,
                    "sortable": True,
                    "nullable": column.nullable,
                    "widget": options.widget if options else None,
                    "recordLink": options.record_link if options else True,
                    "statusBadge": options.status_badge.metadata() if options and options.status_badge else None,
                    "code": options.code.metadata() if options and options.code else None,
                    "fileUpload": ({"multiple": options.file_upload.multiple,
                                    "maxFiles": options.file_upload.max_files,
                                    "maxSizeBytes": options.file_upload.max_size_bytes,
                                    "maxTotalBytes": options.file_upload.max_total_bytes,
                                    "accept": options.file_upload.accept,
                                    "preview": options.file_upload.preview,
                                    "allowPaste": options.file_upload.allow_paste,
                                    "mockOnly": True}
                                   if options and options.file_upload else None),
                    "help": options.help if options else None,
                    "maxLength": getattr(column.type, "length", None) if kind == "string" else None,
                    "precision": getattr(column.type, "precision", None) if kind == "number" else None,
                    "scale": getattr(column.type, "scale", None) if kind == "number" else None,
                    "filterWidth": options.filter_width if options else None,
                    "dependency": ({"source": options.dependency.source,
                                    "bridge": options.dependency.bridge}
                                   if options and options.dependency else None),
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
                "primaryKey": False, "sortable": False, "nullable": True, "widget": virtual.widget, "fileUpload": None, "help": None,
                "maxLength": None, "precision": None, "scale": None, "filterWidth": None,
                "dependency": None,
                "filterOperators": [], "options": None, "relation": None,
                "components": {}, "span": 1, "views": views,
            })
        return {
            "id": self.resource.name,
            "label": self.resource.label,
            "icon": icon_metadata(self.resource.icon),
            "navigation": self.resource.navigation,
            "navigationOrder": self.resource.navigation_order,
            "primaryKey": self.identity_field,
            "primaryKeys": list(self.pk_names),
            "versionField": self.resource.version_field,
            "uploads": self.resource._uploads_enabled,
            "uploadMaxBytes": self.resource._upload_max_bytes if self.resource._uploads_enabled else None,
            "titleField": self._title_field(),
            "layouts": {mode: [
                {"id": section.id, "title": section.title, "kind": section.kind,
                 "fields": section.fields, "visibleIf": section.visible_if,
                 "defaultOpen": section.default_open, "columns": section.columns}
                for section in items
            ] for mode, items in (("form", self.resource.form_sections),
                                  ("detail", self.resource.detail_sections))},
            "formLayout": self.resource.form_layout,
            "detailLayout": self.resource.detail_layout,
            "pageSize": self.resource.page_size,
            "showSearch": self.resource.show_search,
            "crudViews": self.resource.crud_views,
            "crudSlots": self.resource.crud_slots,
            "skeletons": self.resource.skeletons,
            "crudLayouts": {mode: {"showHeading": layout.get("show_heading", True),
                                    "beforePosition": layout.get("before_position", "after_heading")}
                            for mode, layout in self.resource.crud_layouts.items()},
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
            "jobs": [
                {"name": a.name, "label": a.label or a.name.replace("_", " ").title(),
                 "confirmation": a.confirmation, "cancellable": a.cancellable}
                for a in self.resource.jobs
            ],
            "actions": [
                {"name": a.name, "label": a.label or a.name.replace("_", " ").title(),
                 "variant": a.variant, "confirmation": a.confirmation,
                 "position": a.position, "appearance": a.appearance,
                 "component": a.component, "dialog": a.dialog, "icon": icon_metadata(a.icon), "kind": a.kind}
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

    def _label(self, row: Any, fields: set[str]) -> str:
        if self.resource.label_factory is not None and all(
            name in fields for name, field in self.resource.fields.items()
            if field.read_role is not None or field.read_when is not None
        ) and all(
            name in fields for name, field in self.resource.virtual_fields.items() if field.read_role is not None
        ):
            label = self.resource.label_factory(row)
            if not isinstance(label, str):
                raise AdminError(500, "label_factory must return a string", "invalid_label")
            return label
        title = self._title_field()
        if self.composite and (title not in fields or title == self.pk_name):
            return " / ".join(str(getattr(row, name)) for name in self.pk_names if name in fields)
        return str(getattr(row, title if title in fields else self.pk_name))

    def _guess_title(self) -> str:
        for name in ("name", "title", "email", "username", self.pk_name):
            if name in self.columns and self.visible(name):
                return name
        return self.pk_name

    def parsed_payload(self, payload: Mapping[str, Any], *, create: bool) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise AdminError(422, "Expected JSON object", "validation_error")
        unexpected = set(payload) - set(self.columns) - set(self.resource.virtual_fields)
        forbidden = [name for name in payload if name in self.columns and not self.writable(name, create=create)]
        if unexpected or forbidden:
            raise AdminError(422, "Unknown or read-only fields", "validation_error", {
                "fields": sorted(unexpected | set(forbidden))
            })
        out = {}
        for name, value in payload.items():
            # A mock picker must not become a writable metadata injection path.
            if name in self.columns and (config := self._field(name)) is not None and config.file_upload is not None:
                raise AdminError(422, "Mock file fields are not writable; use an explicit verified upload workflow", "validation_error")
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
                if self.writable(name, create=True) and not col.nullable and col.default is None
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

    def _search(self, stmt: Any, query: str, fields: set[str] | None, *, use_title: bool = False) -> Any:
        title = self._title_field()
        candidates = self.resource.search_fields or ([title] if use_title else [])

        def searchable(name: str) -> bool:
            field = self._field(name)
            return (fields is None or name in fields) and (field is None or field.read_when is None)

        columns = [name for name in candidates if searchable(name)
                   and column_kind(self.columns[name]) in ("string", "enum")]
        if columns:
            escaped = query.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            return stmt.where(or_(*(func.lower(getattr(self.resource.model, name)).like(
                f"%{escaped}%", escape="\\") for name in columns)))
        if use_title and self.composite and all(searchable(name) for name in self.pk_names):
            try:
                return stmt.where(self.identity_predicate(query))
            except AdminError:
                pass
        if use_title and not self.composite and title == self.pk_name and searchable(title):
            try:
                return stmt.where(getattr(self.resource.model, self.pk_name) == self.pk_value(query))
            except AdminError:
                pass
        return stmt.where(False) if candidates else stmt

    async def list(
        self, session: Any, principal: Principal, *, offset: int = 0,
        limit: int | None = None, q: str = "", sort: str | None = None,
        desc: bool = False, filters: dict[str, str] | None = None,
        allowed_fields: set[str] | None = None,
        filter_fields: set[str] | None = None,
        per_record_fields: Any = None,
    ) -> dict[str, Any]:
        if offset < 0:
            raise AdminError(422, "offset must be nonnegative")
        limit = min(max(limit or self.resource.page_size, 1), 200)
        stmt = select(self.resource.model)
        if q:
            stmt = self._search(stmt, q, allowed_fields)
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
            if (sort not in self.columns or not self.visible(sort) or
                (allowed_fields is not None and sort not in allowed_fields) or
                (self._field(sort) is not None and self._field(sort).read_when is not None)):
                raise AdminError(422, "Invalid sort column")
            key = getattr(self.resource.model, sort)
        else:
            key = getattr(self.resource.model, self.pk_name)
        order = [key]
        if self.composite:
            order.extend(getattr(self.resource.model, name) for name in self.pk_names
                         if name != (sort or self.pk_name))
        stmt = stmt.order_by(*(item.desc() if desc else item.asc() for item in order)).limit(limit).offset(offset)
        result = await maybe_await(session.execute(stmt))
        serialized = []
        for row in result.scalars().all():
            fields = await per_record_fields(row) if per_record_fields is not None else allowed_fields
            serialized.append(self.serialize(row, fields))
        return {"items": serialized, "total": total, "offset": offset, "limit": limit}

    async def get(self, session: Any, identifier: str, principal: Principal, *,
                  lock: bool | None = None) -> Any:
        stmt = await self._scope(
            select(self.resource.model).where(self.identity_predicate(identifier)),
            principal,
        )
        if lock is not None:
            stmt = stmt.with_for_update(read=not lock, of=self.resource.model)
        result = await maybe_await(session.execute(stmt))
        record = result.scalar_one_or_none()
        if record is None:
            raise AdminError(404, "Record not found", "not_found")
        return record

    async def _audit(self, session: Any, record: Any, operation: str,
                     principal: Principal | None, field_names: list[str]) -> None:
        if not self.resource._audit_enabled:
            return
        from .audit import AuditEntry
        session.add(AuditEntry(
            resource=self.resource.name, record_id=self.persisted_identifier(record, 150),
            actor_id=str(principal.id) if principal is not None else "system",
            operation=operation, field_names=sorted(set(field_names)),
        ))

    @asynccontextmanager
    async def _handler_transaction(self, session: Any):
        # Application handlers are trusted code, but the framework owns commit.
        if not session.in_transaction():
            await maybe_await(session.begin())
        target = getattr(session, "sync_session", session)
        def reject_commit(_session):
            raise AdminError(500, "CRUD handlers must not commit transactions", "handler_transaction_error")
        created: list[Any] = []
        rolled_back = False
        def remember_new(_session, instance):
            created.append(instance)
        def remember_rollback(_session):
            nonlocal rolled_back
            rolled_back = True
        event.listen(target, "before_commit", reject_commit)
        event.listen(target, "pending_to_persistent", remember_new)
        event.listen(target, "after_rollback", remember_rollback)
        try:
            async with self._transaction_errors(session):
                yield created
                if rolled_back:
                    raise AdminError(500, "CRUD handlers must not roll back transactions", "handler_transaction_error")
        finally:
            event.remove(target, "before_commit", reject_commit)
            event.remove(target, "pending_to_persistent", remember_new)
            event.remove(target, "after_rollback", remember_rollback)

    async def _stage_create(self, session: Any, payload: dict[str, Any],
                            principal: Principal | None = None, *, context: OperationContext | None = None) -> Any:
        parsed = self.parsed_payload(payload, create=True)
        if context is not None:
            context.payload = parsed.copy()
        mapped = {key: value for key, value in parsed.items() if key in self.columns}
        for key, factory in self.resource._server_defaults.items():
            mapped[key] = factory()
        if self.resource.create_handler is not None:
            ctx = context or OperationContext("create", self.resource.name, principal, session, payload=parsed.copy())
            async with self._handler_transaction(session) as created:
                record = await maybe_await(self.resource.create_handler(ctx))
                if not isinstance(record, self.resource.model):
                    raise AdminError(500, "create_handler must return a mapped resource instance", "handler_output_error")
                state = inspect(record)
                if (state.deleted or state.detached or (state.persistent and not any(row is record for row in created))
                        or (state.session is not None and state.session is not getattr(session, "sync_session", session))):
                    raise AdminError(500, "create_handler must return a new instance in the current session", "handler_output_error")
                for key in self.resource._server_defaults:
                    setattr(record, key, mapped[key])
        else:
            record = self.resource.model(**mapped)
        for key, value in parsed.items():
            if key in self.resource.virtual_fields:
                await maybe_await(self.resource.virtual_fields[key].setter(record, value))
        session.add(record)
        if context is not None:
            context.record = record
            context.payload = parsed.copy()
        return record

    async def _flush_create(self, session: Any, record: Any, payload: dict[str, Any],
                            principal: Principal | None) -> None:
        async with self._transaction_errors(session):
            await maybe_await(session.flush())
        if self.resource._uploads_enabled:
            self.persisted_identifier(record, 120)
        await self._audit(session, record, "create", principal, list(payload))

    async def create(self, session: Any, payload: dict[str, Any],
                     principal: Principal | None = None) -> dict[str, Any]:
        record = await self._stage_create(session, payload, principal)
        if self.resource._audit_enabled or self.resource._uploads_enabled:
            await self._flush_create(session, record, payload, principal)
        await self._commit(session)
        await maybe_await(session.refresh(record))
        return self.serialize(record)

    async def _stage_update(self, session: Any, record: Any, payload: dict[str, Any],
                            principal: Principal | None, *, context: OperationContext | None = None) -> set[str]:
        parsed = self.parsed_payload(payload, create=False)
        if context is not None:
            context.payload = parsed.copy()
        before = None
        if self.resource.update_handler is not None:
            from copy import deepcopy
            before = {name: deepcopy(getattr(record, name)) for name in self.columns}
            identity = tuple(getattr(record, name) for name in self.pk_names)
            ctx = context or OperationContext("update", self.resource.name, principal, session, record=record, payload=parsed.copy())
            async with self._handler_transaction(session):
                await maybe_await(self.resource.update_handler(ctx))
                state = inspect(record)
                if (ctx.record is not record or state.deleted or state.detached or not state.persistent or record in session.deleted
                        or tuple(getattr(record, name) for name in self.pk_names) != identity):
                    raise AdminError(500, "update_handler cannot replace or delete the resource identity", "handler_output_error")
        for name, value in parsed.items():
            if name in self.resource.virtual_fields:
                await maybe_await(self.resource.virtual_fields[name].setter(record, value))
            elif self.resource.update_handler is None:
                setattr(record, name, value)
        for key, factory in self.resource._server_onupdate.items():
            setattr(record, key, factory())
        if context is not None:
            context.payload = parsed.copy()
        await self._audit(session, record, "update", principal, list(payload))
        state = inspect(record)
        changed = {name for name in self.columns if state.attrs[name].history.has_changes()}
        if before is not None:
            changed.update(name for name in self.columns if getattr(record, name) != before[name])
        return changed

    async def update(self, session: Any, record: Any, payload: dict[str, Any],
                     principal: Principal | None = None) -> dict[str, Any]:
        await self._stage_update(session, record, payload, principal)
        async with self._transaction_errors(session):
            await maybe_await(session.flush())
        await maybe_await(session.refresh(record))
        result = self.serialize(record)
        await self._commit(session)
        return result

    async def delete(self, session: Any, record: Any,
                     principal: Principal | None = None) -> None:
        await self._audit(session, record, "delete", principal, [])
        await maybe_await(session.delete(record))
        await self._commit(session)

    async def _commit(self, session: Any) -> None:
        async with self._transaction_errors(session):
            await maybe_await(session.commit())

    @asynccontextmanager
    async def _transaction_errors(self, session: Any):
        try:
            yield
        except StaleDataError as exc:
            await maybe_await(session.rollback())
            raise AdminError(412, "Record changed since it was loaded", "precondition_failed") from exc
        except IntegrityError as exc:
            await maybe_await(session.rollback())
            raise AdminError(409, "Database constraint prevents this operation. The record may be referenced by other records or a value must be unique.", "integrity_error") from exc
        except SQLAlchemyError:
            await maybe_await(session.rollback())
            raise

    async def options(
        self, session: Any, principal: Principal, query: str = "", limit: int = 30,
        ids: list[str] | None = None, *, allowed_fields: set[str],
        per_record_fields: Callable[[Any], Awaitable[set[str] | None]],
    ) -> list[dict[str, Any]]:
        if len(query) > 200:
            raise AdminError(422, "Search text too long", "validation_error")
        if not set(self.pk_names).issubset(allowed_fields):
            return []
        stmt = select(self.resource.model)
        if ids:
            if len(ids) > 100:
                raise AdminError(422, "Too many selected IDs", "validation_error")
            stmt = stmt.where(self.identities_predicate(ids))
        elif query:
            stmt = self._search(stmt, query, allowed_fields, use_title=True)
        stmt = (await self._scope(stmt, principal)).order_by(*self.identity_order())
        options: list[dict[str, Any]] = []
        limit = min(limit, 100)
        offset = 0
        batch_size = 100
        while len(options) < limit:
            rows = (await maybe_await(session.execute(stmt.limit(batch_size).offset(offset)))).scalars().all()
            for row in rows:
                fields = await per_record_fields(row)
                if fields is None or not set(self.pk_names).issubset(fields):
                    continue
                options.append({"value": self.record_identifier(row) if self.composite else jsonable_encoder(getattr(row, self.pk_name)),
                                "label": self._label(row, fields)})
                if len(options) == limit:
                    break
            if len(rows) < batch_size:
                break
            offset += batch_size
        return options

    async def relation(
        self, session: Any, principal: Principal, record: Any, name: str,
        target: "MapperAdapter", offset: int = 0, limit: int = 20, query: str = "",
        allowed_fields: set[str] | None = None,
        per_record_fields: Any = None,
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
            stmt = target._search(stmt, query, allowed_fields, use_title=True)
        count = (await maybe_await(session.execute(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        ))).scalar_one()
        results = await maybe_await(session.execute(
            stmt.order_by(*target.identity_order()).offset(offset).limit(min(limit, 100))
        ))
        items = []
        for row in results.scalars():
            fields = await per_record_fields(row) if per_record_fields is not None else allowed_fields
            items.append(target.serialize(row, fields))
        return {"items": items, "total": count, "offset": offset, "limit": limit}
