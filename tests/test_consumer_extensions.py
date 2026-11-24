"""Consumer extension contracts: composite read identities, CRUD handlers and binary bridges."""
import json
from urllib.parse import quote

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from pyntral import Admin, CallbackAuth, Principal, Resource, Field, Bridge, BridgeUpload, AuditBase, AuditEntry, AuditFeature
from pyntral.orm import AdminError
from pyntral.typegen import render_bridge_types


class Base(DeclarativeBase):
    pass


class Link(Base):
    __tablename__ = "consumer_links"
    speaker: Mapped[int] = mapped_column(primary_key=True)
    entity: Mapped[str] = mapped_column(String(100), primary_key=True)
    note: Mapped[str] = mapped_column(String(80))


class Item(Base):
    __tablename__ = "consumer_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(80))


@pytest.fixture
def setup():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    AuditBase.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    async def login(username, password):
        return Principal(id=username, username=username, roles=["admin"])
    app = FastAPI()
    admin = Admin(app, session_factory=sessions, auth=CallbackAuth(login),
                  secret_key="consumer-extension-test-secret" * 2, secure_cookie=False)
    yield app, admin, sessions
    engine.dispose()


def authenticated(client):
    response = client.post("/admin/auth/login", json={"username": "admin", "password": "x"})
    return {"X-CSRF-Token": response.json()["csrf"]}


def test_composite_read_only_and_scope(setup):
    app, admin, sessions = setup
    admin.add_resource(Resource(Link, name="links", allow_create=False, allow_edit=False, allow_delete=False,
                                scope=lambda principal, stmt: stmt.where(Link.speaker == 1),
                                fields={"entity": Field(read_when=lambda principal, row: row.note != "private")},
                                crud_slots={"list": {"before": "summary"}}))
    with sessions() as session:
        session.add_all([Link(speaker=1, entity="a/b?ü", note="visible"),
                         Link(speaker=1, entity="z", note="private"), Link(speaker=2, entity="secret", note="other")])
        session.commit()
        forbidden_id = admin.resources["links"].record_identifier(session.get(Link, (2, "secret")))
    with TestClient(app) as client:
        headers = authenticated(client)
        schema = client.get("/admin/api/schema").json()["resources"][0]
        assert schema["primaryKeys"] == ["speaker", "entity"]
        assert schema["primaryKey"] == "__pyntral_id"
        assert schema["crudSlots"] == {"list": {"before": "summary"}}
        assert not any(schema["capabilities"][k] for k in ("create", "edit", "delete"))
        path = "/admin/api/resources/links"
        result = client.get(path).json()
        assert result["total"] == 2
        first, second = result["items"]
        identifier = first["__pyntral_id"]
        assert first["entity"] == "a/b?ü" and "/" not in identifier
        assert "__pyntral_id" not in second and "entity" not in second
        assert client.get(path + "/" + identifier).json()["record"]["entity"] == "a/b?ü"
        assert client.get(path + "/" + forbidden_id).status_code == 404
        assert client.get(path + "/bad!").status_code == 422
        assert client.post(path, json={}, headers=headers).status_code == 403
        assert client.patch(path + "/" + identifier, json={}, headers=headers).status_code == 403
        assert client.delete(path + "/" + identifier, headers=headers).status_code == 403
        assert len(client.get(path + "/options").json()["items"]) == 1
        exported = client.get(path + "/export?format=json").json()
        assert all("__pyntral_id" not in row for row in exported)


def test_handler_transaction_and_field_authorization(setup):
    app, admin, sessions = setup
    calls = []
    def create(ctx):
        calls.append(("create", ctx.payload.copy()))
        item = Item(name=ctx.payload["name"].upper(), password_hash="server-only")
        return item
    def update(ctx):
        calls.append(("update", ctx.payload.copy()))
        ctx.record.name = ctx.payload["name"].upper()
        if ctx.payload["name"] == "fail":
            ctx.session.flush()
            raise AdminError(422, "Rejected")
        if ctx.payload["name"] == "commit":
            ctx.session.commit()
    admin.add_resource(Resource(Item, name="items", create_handler=create, update_handler=update,
                                fields={"password_hash": Field(visible=False)}, features=[AuditFeature()]))
    with TestClient(app) as client:
        headers = authenticated(client)
        path = "/admin/api/resources/items"
        assert client.post(path, json={"name": "x", "password_hash": "injection"}, headers=headers).status_code in (403, 422)
        assert calls == []
        created = client.post(path, json={"name": "test"}, headers=headers)
        assert created.status_code == 201, created.text
        record = created.json()["record"]
        assert record["name"] == "TEST" and "password_hash" not in record
        detail = path + "/" + str(record["id"])
        assert client.patch(detail, json={"name": "next"}, headers=headers).json()["record"]["name"] == "NEXT"
        assert client.patch(detail, json={"name": "fail"}, headers=headers).status_code == 422
        assert client.patch(detail, json={"name": "commit"}, headers=headers).status_code == 500
        assert client.get(detail).json()["record"]["name"] == "NEXT"
        with sessions() as session:
            assert session.get(Item, record["id"]).password_hash == "server-only"
            assert len(session.scalars(select(AuditEntry)).all()) == 2


def test_binary_bridge_auth_limits_and_generated_types(setup):
    app, admin, _ = setup
    class Input(BaseModel):
        label: str
    class Output(BaseModel):
        name: str
        size: int
        label: str
    calls = []
    def handle(data, ctx):
        calls.append(ctx.file.content)
        return Output(name=ctx.file.filename, size=len(ctx.file.content), label=data.label)
    bridge = Bridge("inspect-file", Input, Output, handle, upload=BridgeUpload(max_bytes=8, content_types=("image/png",)))
    admin.add_bridge(bridge)
    types = render_bridge_types({"inspect-file": bridge})
    assert "file: File" in types and "invokeFileBridge" in types
    with TestClient(app) as client:
        path = "/admin/api/bridge/inspect-file"
        file_headers = {"Content-Type": "image/png", "X-Filename": quote("../file.png"),
                        "X-Pyntral-Input": quote(json.dumps({"label": "test"}))}
        assert client.post(path, content=b"file", headers=file_headers).status_code == 401
        headers = authenticated(client)
        assert client.post(path, content=b"file", headers=file_headers).status_code == 403
        file_headers.update(headers)
        assert client.post(path, content=b"123456789", headers=file_headers).status_code == 413
        assert client.post(path, content=b"file", headers={**file_headers, "Content-Type": "text/plain"}).status_code == 415
        assert client.post(path, content=b"file", headers={**file_headers, "X-Pyntral-Input": "%7B%7D"}).status_code == 422
        assert calls == []
        response = client.post(path, content=b"file", headers=file_headers)
        assert response.status_code == 200, response.text
        assert response.json()["result"] == {"name": "file.png", "size": 4, "label": "test"}
        assert calls == [b"file"]
        schema = client.get("/admin/api/schema").json()["bridges"][0]
        assert schema["upload"] == {"maxBytes": 8, "contentTypes": ["image/png"]}
