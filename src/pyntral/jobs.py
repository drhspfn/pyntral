"""Explicit, bounded, in-process async jobs for admin resource actions.

This is a developer opt-in convenience, not a persistent queue. A job's handler
must be an async function, open its own DB sessions, and cooperate with task
cancellation. Durable work should use a real job worker instead.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable
from uuid import uuid4


@dataclass(slots=True)
class JobContext:
    """Verified principal and fresh session factory, not a request-bound session."""

    principal: Any
    payload: dict[str, Any]
    session_factory: Callable[[], Any]
    _update: Callable[[int, str], None] = field(repr=False)

    def progress(self, percent: int, message: str = "") -> None:
        if isinstance(percent, bool) or not isinstance(percent, int) or not 0 <= percent <= 100:
            raise ValueError("Job progress must be an integer from 0 to 100")
        if not isinstance(message, str) or len(message) > 160:
            raise ValueError("Job progress message must be text with at most 160 characters")
        self._update(percent, message)


@dataclass(slots=True)
class JobAction:
    """An async resource action whose progress can be polled in the admin."""

    name: str
    handler: Callable[[JobContext], Awaitable[Any]]
    label: str | None = None
    confirmation: str | None = None
    timeout_seconds: int = 300
    cancellable: bool = True

    def __post_init__(self) -> None:
        if re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]*", self.name) is None:
            raise ValueError("Job name must be a URL-safe slug")
        if not inspect.iscoroutinefunction(self.handler):
            raise TypeError("JobAction.handler must be async; manage sessions inside the job")
        if isinstance(self.timeout_seconds, bool) or not 1 <= self.timeout_seconds <= 3600:
            raise ValueError("Job timeout must be between 1 and 3600 seconds")


@dataclass(slots=True)
class JobState:
    id: str
    owner_id: str
    resource: str
    action: str
    cancellable: bool
    status: str = "queued"
    progress: int = 0
    message: str = ""
    finished_at: float | None = None

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "resource": self.resource, "action": self.action,
                "status": self.status, "progress": self.progress,
                "message": self.message, "cancellable": self.cancellable}


class JobManager:
    def __init__(self, *, max_running: int = 16, max_retained: int = 128,
                 retention_seconds: int = 3600) -> None:
        if min(max_running, max_retained, retention_seconds) < 1:
            raise ValueError("Job limits must be positive")
        self.max_running, self.max_retained = max_running, max_retained
        self.retention_seconds = retention_seconds
        self._states: dict[str, JobState] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._logger = logging.getLogger("pyntral.jobs")
        self._closing = False

    def _prune(self) -> None:
        now = time.monotonic()
        for key, record in tuple(self._states.items()):
            if record.finished_at is not None and now - record.finished_at >= self.retention_seconds:
                self._states.pop(key, None)
                self._tasks.pop(key, None)
        # Prevent unbounded accumulation of completed jobs even within TTL.
        if len(self._states) > self.max_retained:
            for key, record in tuple(self._states.items()):
                if len(self._states) <= self.max_retained:
                    break
                if record.finished_at is not None:
                    self._states.pop(key, None)
                    self._tasks.pop(key, None)

    def submit(self, action: JobAction, *, resource: str, principal: Any,
               payload: dict[str, Any], session_factory: Callable[[], Any]) -> JobState:
        if self._closing:
            raise RuntimeError("Job manager is shutting down")
        self._prune()
        if sum(record.finished_at is None for record in self._states.values()) >= self.max_running:
            raise RuntimeError("Too many background jobs")
        key = str(uuid4())
        state = JobState(key, str(principal.id), resource, action.name, action.cancellable)
        self._states[key] = state

        def progress(percent: int, message: str) -> None:
            state.progress = percent
            state.message = message

        async def execute() -> None:
            state.status = "running"
            context = JobContext(principal, dict(payload), session_factory, progress)
            try:
                async with asyncio.timeout(action.timeout_seconds):
                    await action.handler(context)
            except asyncio.CancelledError:
                state.status = "cancelled"
                state.message = "Cancelled"
            except TimeoutError:
                state.status = "timed_out"
                state.message = "Job timed out"
            except Exception as exc:
                state.status = "failed"
                state.message = "Job failed"
                self._logger.error("Job failed resource=%s action=%s error_type=%s",
                                   resource, action.name, type(exc).__name__)
            else:
                state.status = "completed"
                state.progress = 100
            finally:
                state.finished_at = time.monotonic()

        self._tasks[key] = asyncio.create_task(execute(), name=f"pyntral-job-{key}")
        return state

    def get(self, key: str, *, owner_id: str) -> JobState | None:
        self._prune()
        state = self._states.get(key)
        return state if state and state.owner_id == owner_id else None

    def cancel(self, key: str, *, owner_id: str) -> JobState | None:
        state = self.get(key, owner_id=owner_id)
        if state and state.cancellable and state.finished_at is None:
            task = self._tasks.get(key)
            if task is not None:
                task.cancel()
        return state

    async def close(self) -> None:
        self._closing = True
        for task in self._tasks.values():
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._prune()
