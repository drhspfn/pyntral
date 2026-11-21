"""Composable features with explicit registration, collisions and safety rules."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import inspect

from .auth import hash_password, maybe_await
from .resources import Action, Field
from .virtual import VirtualField


@runtime_checkable
class ResourceFeature(Protocol):
    def apply(self, resource: Any) -> None: ...


def _require_column(resource: Any, name: str) -> None:
    if name not in {prop.key for prop in inspect(resource.model).column_attrs}:
        raise ValueError(f"{resource.model.__name__} has no mapped column {name!r}")


@dataclass(slots=True)
class PasswordFeature:
    """Create a write-only, hashed password input without returning its value."""

    input_field: str = "new_password"
    storage_field: str = "password_hash"
    minimum_length: int = 8

    def apply(self, resource: Any) -> None:
        _require_column(resource, self.storage_field)
        if self.input_field in resource.virtual_fields or self.input_field == self.storage_field:
            raise ValueError(f"PasswordFeature conflicts on {self.input_field}")
        if self.minimum_length < 8:
            raise ValueError("Password minimum_length must be at least 8")
        old = resource.fields.get(self.storage_field)
        if old is not None and old.visible:
            raise ValueError("Password storage field must not be exposed")
        resource.fields[self.storage_field] = Field(visible=False)

        minimum = self.minimum_length
        storage = self.storage_field

        def set_password(record: Any, raw: Any) -> None:
            if not isinstance(raw, str) or len(raw) < minimum:
                from .orm import AdminError
                raise AdminError(422, "Password does not meet minimum length", "validation_error")
            setattr(record, storage, hash_password(raw))

        resource.virtual_fields[self.input_field] = VirtualField(
            kind="string", label="Set password", setter=set_password, required=True,
        )


@dataclass(slots=True)
class SoftDeleteFeature:
    """Add explicit archive/restore actions; disable destructive delete by default."""

    field: str = "deleted_at"
    archive_name: str = "archive"
    restore_name: str = "restore"
    disable_hard_delete: bool = True

    def apply(self, resource: Any) -> None:
        _require_column(resource, self.field)
        existing = {action.name for action in resource.actions}
        if self.archive_name == self.restore_name or {self.archive_name, self.restore_name} & existing:
            raise ValueError("SoftDeleteFeature action name conflict")
        column = self.field

        async def archive(record, session, _principal, _payload):
            setattr(record, column, dt.datetime.now(dt.timezone.utc))
            await maybe_await(session.commit())
            return {"archived": True}

        async def restore(record, session, _principal, _payload):
            setattr(record, column, None)
            await maybe_await(session.commit())
            return {"restored": True}

        resource.actions.extend([
            Action(self.archive_name, archive, label="Archive", variant="danger",
                   confirmation="Archive this record?", visible=lambda _p, r: getattr(r, column) is None),
            Action(self.restore_name, restore, label="Restore",
                   visible=lambda _p, r: getattr(r, column) is not None),
        ])
        if self.disable_hard_delete:
            resource.allow_delete = False


@dataclass(slots=True)
class TimestampFeature:
    """Server-managed create/update timestamps without trusting client values."""

    created_field: str = "created_at"
    updated_field: str = "updated_at"

    def apply(self, resource: Any) -> None:
        for column in (self.created_field, self.updated_field):
            _require_column(resource, column)
            existing = resource.fields.get(column)
            if existing is not None and existing.visible is False:
                raise ValueError("TimestampFeature requires visible timestamp metadata")
            resource.fields[column] = Field(readonly=True)
        now = lambda: dt.datetime.now(dt.timezone.utc)
        if self.created_field in resource._server_defaults or self.updated_field in resource._server_onupdate:
            raise ValueError("TimestampFeature conflicts with a timestamp writer")
        resource._server_defaults[self.created_field] = now
        resource._server_defaults[self.updated_field] = now
        resource._server_onupdate[self.updated_field] = now


@dataclass(slots=True)
class AuditFeature:
    """Write an audit row in the same database transaction as normal CRUD."""

    def apply(self, resource: Any) -> None:
        if resource._audit_enabled:
            raise ValueError("Duplicate AuditFeature on a resource")
        resource._audit_enabled = True


@dataclass(slots=True)
class UploadFeature:
    """Enable authenticated attachments for one resource."""

    max_bytes: int = 10 * 1024 * 1024

    def apply(self, resource: Any) -> None:
        if resource._uploads_enabled:
            raise ValueError("Duplicate UploadFeature")
        if not 1 <= self.max_bytes <= 100 * 1024 * 1024:
            raise ValueError("Upload max_bytes must be 1..104857600")
        resource._uploads_enabled = True
        resource._upload_max_bytes = self.max_bytes
