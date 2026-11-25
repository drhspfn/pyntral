"""Consumer extension contracts: composite read identities, CRUD handlers and binary bridges."""
import json
from urllib.parse import quote

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import String, ForeignKeyConstraint, ForeignKey, Table, Column, create_engine, select, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, relationship
from sqlalchemy.pool import StaticPool

from pyntral import Admin, CallbackAuth, Principal, Resource, Field, Bridge, BridgeUpload, AuditBase, AuditEntry, AuditFeature, Action, ResourceHook, ResourceUpdated, ResourceCreated, ResourceDeleted, UploadFeature, UploadBase, LocalStorage
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


class Child(Base):
    __tablename__ = "consumer_children"
    id: Mapped[int] = mapped_column(primary_key=True)
    speaker: Mapped[int]
    entity: Mapped[str] = mapped_column(String(100))
    __table_args__ = (ForeignKeyConstraint(["speaker", "entity"], ["consumer_links.speaker", "consumer_links.entity"]),)
    link: Mapped[Link] = relationship()


group_links = Table("consumer_group_links", Base.metadata,
                    Column("group_id", ForeignKey("consumer_groups.id"), primary_key=True),
                    Column("speaker", primary_key=True, type_=Link.__table__.c.speaker.type),
                    Column("entity", primary_key=True, type_=String(100)),
                    ForeignKeyConstraint(["speaker", "entity"], ["consumer_links.speaker", "consumer_links.entity"]))


class Group(Base):
    __tablename__ = "consumer_groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    links: Mapped[list[Link]] = relationship(secondary=group_links)


@pytest.fixture
def setup(tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    AuditBase.metadata.create_all(engine)
    UploadBase.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    async def login(username, password):
        return Principal(id=username, username=username, roles=["admin"])
    app = FastAPI()
    admin = Admin(app, session_factory=sessions, auth=CallbackAuth(login),
                  secret_key="consumer-extension-test-secret" * 2, secure_cookie=False,
                  storage=LocalStorage(tmp_path / "objects"))
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


def test_composite_crud_handlers_actions_and_uploads(setup):
    app, admin, sessions = setup
    seen = []
    contexts = []
    def before(ctx):
        contexts.append(ctx)
        ctx.payload["note"] = ctx.payload["note"].strip()
        seen.append("before")
    def handler(ctx):
        assert ctx is contexts[-1]
        ctx.record.note = ctx.payload["note"].upper()
        ctx.session.flush()
        seen.append("handler")
    def after(ctx):
        assert ctx is contexts[-1]
        assert ctx.payload == {"note": "changed"}
        seen.append("after")
    def action(record, session, principal, payload):
        return {"entity": record.entity}
    def bulk(records, session, principal, payload):
        return {"entities": sorted(row.entity for row in records)}
    admin.add_resource(Resource(Link, name="links", scope=lambda principal, stmt: stmt.where(Link.speaker == 1),
                                update_handler=handler,
                                hooks=[ResourceHook(before_update=before, after_update=after)],
                                actions=[Action("inspect", action), Action("inspect-many", bulk, kind="bulk")],
                                features=[AuditFeature(), UploadFeature(max_bytes=32)]))
    events = []
    admin.events.subscribe("resource.*", events.append, resource="links")
    with TestClient(app) as client:
        headers = authenticated(client)
        path = "/admin/api/resources/links"
        schema = client.get("/admin/api/schema").json()["resources"][0]
        key_fields = [field for field in schema["fields"] if field["primaryKey"]]
        assert len(key_fields) == 2
        assert all(field["views"]["create"]["visible"] and not field["views"]["create"]["readonly"] for field in key_fields)
        assert all(field["views"]["edit"]["readonly"] for field in key_fields)
        assert client.post(path, json={"speaker": 1, "note": "x"}, headers=headers).status_code == 422
        one = client.post(path, json={"speaker": 1, "entity": "a/b?ü", "note": "first"}, headers=headers)
        assert one.status_code == 201, one.text
        two = client.post(path, json={"speaker": 1, "entity": "second", "note": "second"}, headers=headers)
        assert two.status_code == 201, two.text
        first_id = one.json()["record"]["__pyntral_id"]
        second_id = two.json()["record"]["__pyntral_id"]
        assert first_id != second_id
        assert client.post(path, json={"speaker": 1, "entity": "second", "note": "duplicate"}, headers=headers).status_code == 409
        assert client.post(path, json={"speaker": 2, "entity": "outside", "note": "x"}, headers=headers).status_code == 404
        assert [item["value"] for item in client.get(path + "/options?ids=" + first_id).json()["items"]] == [first_id]
        actions = client.get(path).json()["actionsByRecord"]
        assert actions == {first_id: ["inspect"], second_id: ["inspect"]}
        detail = path + "/" + first_id
        assert client.post(detail + "/actions/inspect", json={}, headers=headers).json()["result"] == {"entity": "a/b?ü"}
        bulk_result = client.post(path + "/actions/inspect-many", json={"ids": [first_id, second_id]}, headers=headers)
        assert bulk_result.status_code == 200, bulk_result.text
        assert bulk_result.json()["result"]["entities"] == ["a/b?ü", "second"]
        assert client.patch(detail, json={"entity": "new"}, headers=headers).status_code == 422
        edited = client.patch(detail, json={"note": " changed "}, headers=headers)
        assert edited.status_code == 200, edited.text
        assert edited.json()["record"]["note"] == "CHANGED"
        assert edited.json()["record"]["__pyntral_id"] == first_id
        assert seen == ["before", "handler", "after"]
        assert client.get(path + "/" + second_id).json()["record"]["note"] == "second"
        assert isinstance(events[-1], ResourceUpdated)
        assert events[-1].record_id == first_id
        assert [field.name for field in events[-1].fields] == ["note"]
        upload = client.post(detail + "/uploads", content=b"abc", headers={**headers, "X-Filename": "sample.bin"})
        assert upload.status_code == 201, upload.text
        upload_id = upload.json()["id"]
        assert client.get(detail + "/uploads").json()["items"][0]["id"] == upload_id
        assert client.get("/admin/api/uploads/" + upload_id).content == b"abc"
        assert client.delete(detail, headers=headers).status_code == 200
        assert client.get(detail).status_code == 404
        assert client.get("/admin/api/uploads/" + upload_id).status_code == 404
        assert isinstance(events[-1], ResourceDeleted) and events[-1].record_id == first_id
        with sessions() as session:
            assert session.get(Link, (1, "second")) is not None
            rows = session.scalars(select(AuditEntry).where(AuditEntry.record_id == first_id)).all()
            assert [row.operation for row in rows] == ["create", "update", "delete"]


def test_composite_foreign_keys_and_many_to_many(setup):
    app, admin, sessions = setup
    admin.add_resource(Resource(Link, name="links", scope=lambda principal, stmt: stmt.where(Link.speaker == 1)))
    admin.add_resource(Resource(Child, name="children"))
    admin.add_resource(Resource(Group, name="groups"))
    with sessions() as session:
        session.add_all([Link(speaker=1, entity="a", note="a"), Link(speaker=1, entity="b", note="b"),
                         Link(speaker=2, entity="a", note="outside"), Group(name="demo")])
        session.commit()
    with TestClient(app) as client:
        headers = authenticated(client)
        path = "/admin/api/resources"
        keys = {item["entity"]: item["__pyntral_id"] for item in client.get(path + "/links").json()["items"]}
        assert client.post(path + "/children", json={"speaker": 2, "entity": "a"}, headers=headers).status_code == 409
        assert client.post(path + "/children", json={"speaker": 1}, headers=headers).status_code == 422
        response = client.post(path + "/children", json={"speaker": 1, "entity": "a"}, headers=headers)
        assert response.status_code == 201, response.text
        detail = path + "/children/" + str(response.json()["record"]["id"])
        assert client.patch(detail, json={"entity": "b"}, headers=headers).status_code == 200
        assert client.patch(detail, json={"speaker": 2}, headers=headers).status_code == 409
        assert client.get(detail + "/relationships/link").json()["items"][0]["__pyntral_id"] == keys["b"]
        relation = path + "/groups/1/relationships/links"
        for identifier in keys.values():
            response = client.post(relation + "/attach", json={"id": identifier}, headers=headers)
            assert response.status_code == 200, response.text
        assert client.get(relation).json()["total"] == 2
        assert client.post(relation + "/detach", json={"id": keys["a"]}, headers=headers).status_code == 200
        assert client.get(relation).json()["items"][0]["__pyntral_id"] == keys["b"]


@pytest.mark.asyncio
async def test_async_composite_versioned_handler(tmp_path):
    pytest.importorskip("greenlet")
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    class VersionedBase(DeclarativeBase):
        pass

    class Draft(VersionedBase):
        __tablename__ = "async_composite_drafts"
        tenant: Mapped[int] = mapped_column(primary_key=True)
        key: Mapped[str] = mapped_column(String(80), primary_key=True)
        title: Mapped[str] = mapped_column(String(80))
        version: Mapped[int] = mapped_column(default=1, nullable=False)
        __mapper_args__ = {"version_id_col": version}

    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'async-composite.db').as_posix()}")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(VersionedBase.metadata.create_all)
        sessions = async_sessionmaker(engine)
        app = FastAPI()
        admin = Admin(app, session_factory=sessions,
                      auth=CallbackAuth(lambda *_: Principal(id="operator", username="operator")),
                      secret_key="s" * 64, secure_cookie=False, require_async_sessions=True)
        async def edit(ctx):
            ctx.record.title = ctx.payload["title"].upper()
            await ctx.session.flush()
        admin.add_resource(Resource(Draft, name="drafts", update_handler=edit, version_field="version"))
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://fixture") as client:
                auth = await client.post("/admin/auth/login", json={"username": "operator", "password": "fixture"})
                headers = {"X-CSRF-Token": auth.json()["csrf"]}
                path = "/admin/api/resources/drafts"
                created = await client.post(path, json={"tenant": 1, "key": "α/β", "title": "old"}, headers=headers)
                assert created.status_code == 201, created.text
                row = created.json()["record"]
                assert row["version"] == 1
                detail = path + "/" + row["__pyntral_id"]
                edited = await client.patch(detail, json={"title": "new"}, headers={**headers, "If-Match": "1"})
                assert edited.status_code == 200, edited.text
                assert edited.json()["record"]["version"] == 2
                assert edited.json()["record"]["title"] == "NEW"
                stale = await client.patch(detail, json={"title": "stale"}, headers={**headers, "If-Match": "1"})
                assert stale.status_code == 412
                deleted = await client.delete(detail, headers={**headers, "If-Match": "2"})
                assert deleted.status_code == 200, deleted.text
    finally:
        await engine.dispose()


@pytest.mark.parametrize("layout", [
    {"invalid": {}}, {"list": {"unknown": True}}, {"list": {"show_heading": 1}},
    {"list": {"before_position": "below_table"}}, {"list": None},
])
def test_invalid_crud_layout(layout):
    with pytest.raises(ValueError, match="crud_layouts"):
        Resource(Link, crud_layouts=layout)


def test_crud_layout_schema_does_not_change_permissions(setup):
    app, admin, _ = setup
    admin.add_resource(Resource(Link, name="links",
        crud_layouts={"list": {"show_heading": False}, "show": {"before_position": "above_heading"},
                      "create": {}, "edit": {"show_heading": False, "before_position": "above_heading"}},
        crud_slots={"list": {"before": "summary", "after": "footer"}},
        allow_delete=False))
    with TestClient(app) as client:
        authenticated(client)
        schema = client.get("/admin/api/schema").json()["resources"][0]
        assert schema["crudLayouts"] == {
            "list": {"showHeading": False, "beforePosition": "after_heading"},
            "show": {"showHeading": True, "beforePosition": "above_heading"},
            "create": {"showHeading": True, "beforePosition": "after_heading"},
            "edit": {"showHeading": False, "beforePosition": "above_heading"},
        }
        assert schema["crudSlots"]["list"] == {"before": "summary", "after": "footer"}
        assert schema["capabilities"]["create"] and schema["capabilities"]["edit"]
        assert not schema["capabilities"]["delete"]


def test_field_presentation_metadata_and_validation(setup):
    from pyntral import StatusBadgeConfig, CodeFieldConfig
    app, admin, _ = setup
    admin.add_resource(Resource(Item, name="items", skeletons=False,
        fields={"name": Field(record_link=False, status_badge=StatusBadgeConfig(
            tones={"new": "primary"}, labels={"new": "New record"}, auto_tone=False)),
            "password_hash": Field(visible=False, code=CodeFieldConfig())}))
    with TestClient(app) as client:
        authenticated(client)
        schema = client.get("/admin/api/schema").json()["resources"][0]
        assert schema["skeletons"] is False
        fields = {field["name"]: field for field in schema["fields"]}
        assert "password_hash" not in fields
        assert fields["name"]["recordLink"] is False
        assert fields["name"]["statusBadge"] == {
            "tones": {"new": "primary"}, "labels": {"new": "New record"},
            "defaultTone": "neutral", "autoTone": False, "dot": True,
        }
    with pytest.raises(ValueError):
        StatusBadgeConfig(tones={"bad": "arbitrary"})
    with pytest.raises(ValueError):
        CodeFieldConfig(max_height=0)
    with pytest.raises(ValueError):
        Field(status_badge=StatusBadgeConfig(), code=CodeFieldConfig())
    with pytest.raises(TypeError):
        Field(record_link="false")
    with pytest.raises(ValueError):
        Resource(Item, skeletons=1)
