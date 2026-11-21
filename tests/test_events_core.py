"""Event Core: transactional timing, ACL, privacy and delivery semantics."""

from __future__ import annotations

import asyncio
from unittest.mock import patch
from typing import ClassVar

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import ForeignKey, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import StaticPool

from pyntral import (
    Action, Admin, AdminEvent, CallbackAuth, CustomEvent, Field,
    InMemoryEventBus, LocalAuth, Principal, Resource, ResourceCreated, ResourceUpdated,
    ResourceDeleted, ActionExecuted, LoginSucceeded, LoginFailed, LogoutSucceeded,
    hash_password,
)
from pyntral.orm import AdminError


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "event_accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(30), unique=True)
    secret_token: Mapped[str] = mapped_column(String(60), default="KEEP-PRIVATE")
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("event_accounts.id"))
    children: Mapped[list[Account]] = relationship(remote_side=[id])


@pytest.fixture
def setup():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def pragma(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    app = FastAPI()
    bus = InMemoryEventBus()
    admin = Admin(app, session_factory=sessions, auth=LocalAuth("admin", hash_password("long-password")),
                  secret_key="z" * 64, secure_cookie=False, event_bus=bus)
    admin.add_resource(Resource(Account, name="event-accounts", fields={"secret_token": Field(visible=False)}))
    client = TestClient(app)
    response = client.post("/admin/auth/login", json={"username": "admin", "password": "long-password"})
    csrf = {"X-CSRF-Token": response.json()["csrf"]}
    yield client, csrf, admin, sessions
    engine.dispose()


def test_metadata_only_crud_and_noop_update(setup):
    client, headers, admin, sessions = setup
    received = []
    admin.events.subscribe("resource.*", received.append, resource="event-accounts")
    # Verify event is published after commit: subscriber can see the DB state.
    db_names = []
    def db_listener(evt):
        with sessions() as session:
            row = session.get(Account, int(evt.record_id))
            db_names.append(row.name if row else None)
    admin.events.subscribe(ResourceCreated, db_listener)

    result = client.post("/admin/api/resources/event-accounts", json={"name": "x"}, headers=headers)
    assert result.status_code == 201, result.text
    key = result.json()["record"]["id"]
    assert [e.type for e in received] == ["resource.created"]
    assert db_names == ["x"]
    assert received[0].fields[0].name == "name"
    assert received[0].fields[0].kind == "string"
    assert received[0].record_id == str(key)
    assert received[0].actor_id is not None
    assert received[0].correlation_id == result.headers["X-Request-ID"]
    assert received[0].event_id != received[0].correlation_id
    assert "x" not in str(received[0].envelope())
    assert "KEEP-PRIVATE" not in str(received[0].envelope())
    assert all(k not in received[0].envelope() for k in ("values", "payload", "before", "after"))

    assert client.patch(f"/admin/api/resources/event-accounts/{key}", json={"name": "x"}, headers=headers).status_code == 200
    assert len(received) == 1  # noop does not generate an update
    result = client.patch(f"/admin/api/resources/event-accounts/{key}", json={"name": "private-new-value"}, headers=headers)
    assert result.status_code == 200
    assert [e.type for e in received] == ["resource.created", "resource.updated"]
    assert isinstance(received[-1], ResourceUpdated)
    assert [f.name for f in received[-1].fields] == ["name"]
    assert "private-new-value" not in str(received[-1].envelope())

    assert client.delete(f"/admin/api/resources/event-accounts/{key}", headers=headers).status_code == 200
    assert isinstance(received[-1], ResourceDeleted)
    assert received[-1].fields == ()


def test_failed_write_never_emits_event(setup):
    client, headers, admin, _ = setup
    seen = []
    admin.events.subscribe("resource.*", seen.append)
    response = client.post("/admin/api/resources/event-accounts", json={"name": "same"}, headers=headers)
    assert response.status_code == 201
    assert len(seen) == 1
    assert client.post("/admin/api/resources/event-accounts", json={"name": "same"}, headers=headers).status_code == 409
    assert len(seen) == 1
    assert client.post("/admin/api/resources/event-accounts", json={"secret_token": "hack"}, headers=headers).status_code == 422
    assert len(seen) == 1
    assert client.delete("/admin/api/resources/event-accounts/does-not-exist", headers=headers).status_code in (404, 422)
    assert len(seen) == 1


def test_subscriber_failure_isolated_after_commit(setup, caplog):
    client, headers, admin, sessions = setup
    seen = []
    def failed(_):
        raise RuntimeError("SUBSCRIBER-EXCEPTION")
    admin.events.subscribe(ResourceCreated, failed)
    admin.events.subscribe(ResourceCreated, seen.append)
    response = client.post("/admin/api/resources/event-accounts", json={"name": "survives"}, headers=headers)
    assert response.status_code == 201
    assert len(seen) == 1
    with sessions() as session:
        assert session.get(Account, response.json()["record"]["id"]).name == "survives"
    assert "Subscriber failed" in caplog.text


def test_auth_events_redact_credentials(setup):
    client, headers, admin, _ = setup
    received = []
    admin.events.subscribe("auth.*", received.append)
    assert client.post("/admin/auth/login", json={"username": "admin", "password": "wrongSecret"}).status_code == 401
    assert isinstance(received[-1], LoginFailed)
    assert received[-1].actor_id is None
    assert "wrongSecret" not in str(received[-1].envelope())
    signed_in = client.post("/admin/auth/login", json={"username": "admin", "password": "long-password"})
    assert signed_in.status_code == 200
    assert isinstance(received[-1], LoginSucceeded)
    assert received[-1].actor_id
    assert "long-password" not in str(received[-1].envelope())
    assert client.post("/admin/auth/logout", headers={"X-CSRF-Token": signed_in.json()["csrf"]}).status_code == 200
    assert isinstance(received[-1], LogoutSucceeded)


def test_action_event_only_after_handler_success(setup):
    client, headers, admin, _ = setup
    def succeed(record, session, principal, payload):
        return {"secret": "do-not-publish"}
    def fails(record, session, principal, payload):
        raise AdminError(422, "No", "validation_error")
    admin.resources["event-accounts"].resource.actions.extend([
        Action("succeed", succeed), Action("fails", fails),
    ])
    created = client.post("/admin/api/resources/event-accounts", json={"name": "a"}, headers=headers).json()
    seen = []
    admin.events.subscribe(ActionExecuted, seen.append)
    key = created["record"]["id"]
    assert client.post(f"/admin/api/resources/event-accounts/{key}/actions/fails", json={}, headers=headers).status_code == 422
    assert seen == []
    assert client.post(f"/admin/api/resources/event-accounts/{key}/actions/succeed", json={}, headers=headers).status_code == 200
    assert len(seen) == 1
    assert seen[0].action == "succeed" and seen[0].record_id == str(key)
    assert "do-not-publish" not in str(seen[0].envelope())


def test_bus_subscriptions_wildcards_unsubscribe_and_safe_validation():
    bus = InMemoryEventBus()
    got = []
    unsubscribe = bus.subscribe("resource.*", got.append, resource="user*")
    @bus.on(ResourceCreated, resource="users")
    async def typed(event):
        got.append(("typed", event.type))
    event = ResourceCreated(resource="users", record_id="U1")
    report = asyncio.run(bus.publish(event))
    assert report.delivered == 2 and report.failed == 0
    assert len(got) == 2
    unsubscribe()
    assert asyncio.run(bus.publish(event)).delivered == 1
    assert asyncio.run(bus.publish(ResourceCreated(resource="orders", record_id="2"))).delivered == 0
    with pytest.raises(ValidationError):
        ResourceCreated(resource="users", record_id="1", values={"password": "secret"})
    with pytest.raises(TypeError):
        asyncio.run(bus.publish({"type": "resource.created", "values": "private"}))
    assert CustomEvent(name="avatars.published", record_id="abc").envelope()["type"] == "avatars.published"


def test_read_event_record_checks_permissions_and_redacts_fields(setup):
    client, headers, admin, _ = setup
    observed = []
    admin.events.subscribe(ResourceCreated, observed.append)
    key = client.post("/admin/api/resources/event-accounts", json={"name": "public"}, headers=headers).json()["record"]["id"]
    e = observed[0]
    owner = Principal(id="admin", username="admin", roles=["admin"])
    record = asyncio.run(admin.read_event_record(e, owner))
    assert record["id"] == key and record["name"] == "public" and "secret_token" not in record
    class RejectAuth:
        async def resolve(self, principal):
            return principal

        async def authorize(self, principal, name, action, record=None):
            return False
    with patch.object(admin, "auth", RejectAuth()):
        with pytest.raises(AdminError) as exc:
            asyncio.run(admin.read_event_record(e, owner))
        assert exc.value.status == 403
    assert client.delete(f"/admin/api/resources/event-accounts/{key}", headers=headers).status_code == 200
    with pytest.raises(AdminError) as exc:
        asyncio.run(admin.read_event_record(e, owner))
    assert exc.value.status == 404


@pytest.mark.asyncio
async def test_concurrent_async_delivery_is_task_safe():
    bus = InMemoryEventBus()
    seen = []
    @bus.on("resource.updated")
    async def subscribe(event):
        await asyncio.sleep(0)
        seen.append(event.record_id)
    results = await asyncio.gather(*(bus.publish(ResourceUpdated(resource="users", record_id=str(n))) for n in range(40)))
    assert all(r.delivered == 1 for r in results)
    assert sorted(seen, key=int) == [str(n) for n in range(40)]


def test_event_bus_strict_error_policy():
    bus = InMemoryEventBus(on_error="raise")
    bus.subscribe("*", lambda event: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        asyncio.run(bus.publish(ResourceCreated(resource="items", record_id="1")))


def test_resource_events_require_identifiers_and_disallow_custom_payload():
    with pytest.raises(ValidationError):
        ResourceUpdated(resource="users")
    with pytest.raises(ValidationError):
        ResourceDeleted(resource="", record_id="1")
    class AccidentalPayload(AdminEvent):
        event_name: ClassVar[str] = "custom.insecure"  # class-level declaration
        payload: str = "secret"
    with pytest.raises(ValueError, match="metadata only"):
        asyncio.run(InMemoryEventBus().publish(AccidentalPayload()))
