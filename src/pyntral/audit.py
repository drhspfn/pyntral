"""Transactional, metadata-only audit record for mapped CRUD operations."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, String, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class AuditBase(DeclarativeBase):
    pass


class AuditEntry(AuditBase):
    """Metadata only: no previous/current field values, request body or secrets."""

    __tablename__ = "pyntral_audit_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                    default=lambda: str(uuid4()))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                     default=lambda: datetime.now(timezone.utc))
    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    record_id: Mapped[str] = mapped_column(String(150), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(150), nullable=False)
    operation: Mapped[str] = mapped_column(String(20), nullable=False)
    field_names: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
