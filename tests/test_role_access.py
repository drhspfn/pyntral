"""v0.5: role hierarchy, guarded FK selection, field-level ACL and external identity."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import ForeignKey, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import StaticPool

from pyntral import Admin, CallbackAuth, Field, Principal, Resource, RoleAccess, Page, Bridge


class Base(DeclarativeBase):
    pass


class Voice(Base):
    __tablename__ = "v05_voices"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    internal_note: Mapped[str] = mapped_column(String(80), default="private")
    avatars: Mapped[list[Avatar]] = relationship(back_populates="voice")


class Avatar(Base):
    __tablename__ = "v05_avatars"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    voice_id: Mapped[int | None] = mapped_column(ForeignKey("v05_voices.id"))
    voice: Mapped[Voice | None] = relationship(back_populates="avatars")


class BridgeIn(BaseModel):
    id: int


class BridgeOut(BaseModel):
    label: str


@pytest.fixture
def panel():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def fk_on(conn, _record):
        conn.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions() as session:
        session.add_all([Voice(name="A"), Voice(name="B")])
        session.flush()
        session.add(Avatar(name="Main", voice_id=1))
        session.commit()

    async def login(username, password):
        if password != "pass":
            return None
        return Principal(id=username, username=username, roles=[username],
                         email=f"{username}@example.org", attributes={"provider": "password"})

    async def external_login(token):
        if token != "verified-by-provider":
            return None
        return Principal(id="oidc|123", username="external", roles=["avatar-manager"],
                         email="oidc@example.org", attributes={"provider": "oidc"})

    app = FastAPI()
    admin = Admin(app, session_factory=sessions,
                  auth=CallbackAuth(login, login_token=external_login),
                  role_weights={"viewer": 10, "avatar-manager": 20,
                                "voice-editor": 30, "admin": 100},
                  secret_key="secret" * 12, secure_cookie=False)
    admin.add_resource(Resource(Avatar, name="avatars", search_fields=["name"],
                                access=RoleAccess(read="viewer", write="avatar-manager")))
    admin.add_resource(Resource(Voice, name="voices", search_fields=["name"],
                                fields={"internal_note": Field(read_role="admin", write_role="admin")},
                                access=RoleAccess(read="avatar-manager", write="voice-editor", navigation="lock")))
    admin.add_page(Page("audit", "Audit", "audit", min_role="voice-editor"))
    admin.add_bridge(Bridge("private", BridgeIn, BridgeOut,
                            lambda data, ctx: BridgeOut(label="secret"), min_role="voice-editor"))
    with TestClient(app) as client:
        yield client, admin
    engine.dispose()


def login(client, role):
    r = client.post("/admin/auth/login", json={"username": role, "password": "pass"})
    assert r.status_code == 200
    return {"X-CSRF-Token": r.json()["csrf"]}


def test_viewer_locked_navigation_and_no_fk_data(panel):
    client, _ = panel
    csrf = login(client, "viewer")
    me = client.get("/admin/auth/me").json()["user"]
    assert me["email"] == "viewer@example.org" and me["attributes"]["provider"] == "password"
    schema_response = client.get("/admin/api/schema")
    assert schema_response.headers["Cache-Control"] == "no-store"
    schema = schema_response.json()
    assert {r["id"] for r in schema["resources"]} == {"avatars", "voices"}
    avatar = next(r for r in schema["resources"] if r["id"] == "avatars")
    voice = next(r for r in schema["resources"] if r["id"] == "voices")
    assert voice["navigationState"] == "locked" and not voice["fields"]
    assert not voice["capabilities"]["list"] and not voice["capabilities"]["select"]
    assert not avatar["capabilities"]["edit"] and "voice_id" not in [f["name"] for f in avatar["fields"]]
    assert client.get("/admin/api/resources/voices").status_code == 403
    assert client.get("/admin/api/resources/voices/options").status_code == 403
    assert client.get("/admin/api/resources/voices/1").status_code == 403
    assert client.get("/admin/api/resources/avatars/1/relationships/voice").status_code == 403
    rows = client.get("/admin/api/resources/avatars").json()["items"]
    assert "voice_id" not in rows[0]
    assert "voice_id" not in client.get("/admin/api/resources/avatars/1").json()["record"]
    assert client.patch("/admin/api/resources/avatars/1", headers=csrf, json={"voice_id": 2}).status_code == 403
    assert client.get("/admin/api/schema").json()["pages"] == []
    assert client.post("/admin/api/bridge/private", headers=csrf, json={"id": 1}).status_code == 403


def test_avatar_manager_selects_voice_but_cannot_modify_it(panel):
    client, _ = panel
    csrf = login(client, "avatar-manager")
    schema = client.get("/admin/api/schema").json()
    avatar = next(r for r in schema["resources"] if r["id"] == "avatars")
    voice = next(r for r in schema["resources"] if r["id"] == "voices")
    assert avatar["capabilities"]["edit"]
    assert voice["capabilities"]["show"] and voice["capabilities"]["select"]
    assert not voice["capabilities"]["edit"] and not voice["capabilities"]["create"]
    assert "voice_id" in [f["name"] for f in avatar["fields"]]
    assert "internal_note" not in [f["name"] for f in voice["fields"]]
    options = client.get("/admin/api/resources/voices/options?q=B")
    assert options.status_code == 200 and options.json()["items"] == [{"value": 2, "label": "B"}]
    assert client.get("/admin/api/resources/avatars?filter.voice_id=1").json()["total"] == 1
    updated = client.patch("/admin/api/resources/avatars/1", json={"voice_id": 2}, headers=csrf)
    assert updated.status_code == 200, updated.text
    assert updated.json()["record"]["voice_id"] == 2
    assert client.patch("/admin/api/resources/voices/2", json={"name": "New"}, headers=csrf).status_code == 403
    assert client.post("/admin/api/resources/voices", json={"name": "New"}, headers=csrf).status_code == 403
    assert client.patch("/admin/api/resources/avatars/1", json={"voice_id": 12345}, headers=csrf).status_code == 409
    assert client.post("/admin/api/resources/voices/1/actions/unknown", headers=csrf, json={}).status_code == 404
    assert client.get("/admin/api/schema").json()["pages"] == []


def test_role_hierarchy_fields_and_bridge(panel):
    client, _ = panel
    csrf = login(client, "voice-editor")
    data = client.get("/admin/api/schema").json()
    voice = next(r for r in data["resources"] if r["id"] == "voices")
    assert voice["capabilities"]["edit"] and voice["capabilities"]["create"]
    assert not any(f["name"] == "internal_note" for f in voice["fields"])
    assert client.patch("/admin/api/resources/voices/1", json={"internal_note": "leak"}, headers=csrf).status_code == 403
    assert client.post("/admin/api/bridge/private", json={"id": 1}, headers=csrf).json() == {"result": {"label": "secret"}}
    assert {page["name"] for page in data["pages"]} == {"audit"}
    client.post("/admin/auth/logout", headers=csrf)
    csrf = login(client, "admin")
    voice = next(r for r in client.get("/admin/api/schema").json()["resources"] if r["id"] == "voices")
    assert any(f["name"] == "internal_note" for f in voice["fields"])
    changed = client.patch("/admin/api/resources/voices/1", headers=csrf, json={"internal_note": "okay"})
    assert changed.status_code == 200 and changed.json()["record"]["internal_note"] == "okay"


def test_external_identity_token_verified_server_side(panel):
    client, _ = panel
    assert client.post("/admin/auth/external", json={"token": "untrusted", "roles": ["admin"]}).status_code == 401
    assert client.post("/admin/auth/external", json={"token": "verified-by-provider"},
                       headers={"Origin": "https://evil.example"}).status_code == 403
    response = client.post("/admin/auth/external", json={"token": "verified-by-provider", "roles": ["admin"]})
    assert response.status_code == 200
    principal = response.json()["user"]
    assert principal["roles"] == ["avatar-manager"] and principal["id"] == "oidc|123"
    assert client.get("/admin/api/resources/voices").status_code == 200
    assert client.post("/admin/api/resources/voices", json={"name": "X"},
                       headers={"X-CSRF-Token": response.json()["csrf"]}).status_code == 403


def test_invalid_role_configuration(panel):
    _client, admin = panel
    with pytest.raises(ValueError, match="Unknown role"):
        admin.add_resource(Resource(Voice, name="misconfigured", access=RoleAccess(read="undefined")))
