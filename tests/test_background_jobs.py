"""Bounded async job actions have explicit lifecycle and isolation."""
from __future__ import annotations

import asyncio
import pytest

from pyntral import JobAction, JobManager
from pyntral.auth import Principal


@pytest.mark.asyncio
async def test_job_progress_is_owner_only_and_result_values_are_not_returned():
    manager = JobManager(max_running=1)
    actor = Principal(id="one", username="one")
    async def handler(ctx):
        ctx.progress(30, "Starting")
        await asyncio.sleep(0.02)
        ctx.progress(90, "Finishing")
        return {"secret": "never expose this result"}
    action = JobAction("safe-job", handler)
    state = manager.submit(action, resource="users", principal=actor, payload={},
                           session_factory=lambda: None)
    with pytest.raises(RuntimeError, match="Too many background jobs"):
        manager.submit(action, resource="users", principal=actor, payload={},
                       session_factory=lambda: None)
    assert manager.get(state.id, owner_id="another") is None
    await asyncio.sleep(0.08)
    result = manager.get(state.id, owner_id="one")
    assert result is not None and result.status == "completed" and result.progress == 100
    assert "secret" not in str(result.public())
    await manager.close()


@pytest.mark.asyncio
async def test_cancellation_and_shutdown():
    manager = JobManager()
    started = asyncio.Event()
    async def handler(ctx):
        started.set()
        await asyncio.sleep(60)
    action = JobAction("slow-job", handler)
    principal = Principal(id="owner", username="owner")
    state = manager.submit(action, resource="users", principal=principal, payload={},
                           session_factory=lambda: None)
    await started.wait()
    assert manager.cancel(state.id, owner_id="someone-else") is None
    manager.cancel(state.id, owner_id="owner")
    await asyncio.sleep(0)
    assert manager.get(state.id, owner_id="owner").status == "cancelled"
    await manager.close()


@pytest.mark.asyncio
async def test_cancelling_before_start_releases_job_capacity():
    manager = JobManager(max_running=1)
    principal = Principal(id="owner", username="owner")

    async def handler(_context):
        pytest.fail("A queued task must not run after cancellation")

    action = JobAction("queued-job", handler)
    kwargs = dict(resource="users", principal=principal, payload={}, session_factory=lambda: None)
    first = manager.submit(action, **kwargs)
    assert manager.cancel(first.id, owner_id="owner").status == "cancelled"
    assert first.finished_at is not None
    second = manager.submit(action, **kwargs)
    await manager.close()
    assert second.status == "cancelled"
    assert second.finished_at is not None


def test_job_action_validation():
    with pytest.raises(TypeError, match="must be async"):
        JobAction("sync", lambda ctx: None)
    async def handler(ctx):
        return None
    with pytest.raises(ValueError, match="timeout"):
        JobAction("bad", handler, timeout_seconds=0)
