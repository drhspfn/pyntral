"""Revocable admin sessions for one process or a shared SQL database."""
from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Callable, Protocol

from sqlalchemy import Float, JSON, String, delete
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .auth import Principal, maybe_await


@dataclass(frozen=True, slots=True)
class SessionIdentity:
    principal: Principal
    csrf: str
    audience: str
    expires_at: float


class SessionStore(Protocol):
    async def put(self, session_id: str, identity: SessionIdentity) -> None: ...
    async def get(self, session_id: str) -> SessionIdentity | None: ...
    async def revoke(self, session_id: str) -> None: ...


class MemorySessionStore:
    def __init__(self, max_sessions: int = 4096):
        if type(max_sessions) is not int or max_sessions < 1:
            raise ValueError("max_sessions must be a positive integer")
        self.max_sessions = max_sessions
        self._sessions: dict[str, SessionIdentity] = {}
        self._lock = Lock()

    async def put(self, session_id: str, identity: SessionIdentity) -> None:
        with self._lock:
            now = time.time()
            for key in [key for key, value in self._sessions.items() if value.expires_at <= now]:
                del self._sessions[key]
            if len(self._sessions) >= self.max_sessions:
                del self._sessions[next(iter(self._sessions))]
            self._sessions[session_id] = identity

    async def get(self, session_id: str) -> SessionIdentity | None:
        with self._lock:
            identity = self._sessions.get(session_id)
            if identity is not None and identity.expires_at <= time.time():
                del self._sessions[session_id]
                return None
            return identity

    async def revoke(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)


class SessionBase(DeclarativeBase):
    pass


class _SessionRow(SessionBase):
    __tablename__ = "pyntral_sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    principal: Mapped[dict] = mapped_column(JSON)
    csrf: Mapped[str] = mapped_column(String(64))
    audience: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[float] = mapped_column(Float, index=True)


class SQLSessionStore:
    """Use the same session database and signing key on all admin replicas."""

    def __init__(self, session_factory: Callable[[], Any]):
        self.session_factory = session_factory

    async def put(self, session_id: str, identity: SessionIdentity) -> None:
        session = self.session_factory()
        try:
            await maybe_await(session.execute(delete(_SessionRow).where(_SessionRow.expires_at <= time.time())))
            principal = identity.principal.as_dict()
            principal.pop("name")
            principal.pop("role")
            session.add(_SessionRow(id=session_id, principal=principal, csrf=identity.csrf,
                                    audience=identity.audience, expires_at=identity.expires_at))
            await maybe_await(session.commit())
        finally:
            await maybe_await(session.close())

    async def get(self, session_id: str) -> SessionIdentity | None:
        session = self.session_factory()
        try:
            row = await maybe_await(session.get(_SessionRow, session_id))
            if row is None or row.expires_at <= time.time():
                return None
            return SessionIdentity(Principal(**row.principal), row.csrf, row.audience, row.expires_at)
        finally:
            await maybe_await(session.close())

    async def revoke(self, session_id: str) -> None:
        session = self.session_factory()
        try:
            await maybe_await(session.execute(delete(_SessionRow).where(_SessionRow.id == session_id)))
            await maybe_await(session.commit())
        finally:
            await maybe_await(session.close())
