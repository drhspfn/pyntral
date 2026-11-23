"""Revocable admin sessions with a process-local default and a pluggable store."""
from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Protocol

from .auth import Principal


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
