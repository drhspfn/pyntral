from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import ForeignKey, String, create_engine, event, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import StaticPool

from pyntral import (
    Action, Admin, CallbackAuth, Field, LocalAuth, ModelAuth, Principal, Resource,
    hash_password, verify_password,
)


class Base(DeclarativeBase):
    pass


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    secret_token: Mapped[str] = mapped_column(String(100), default="private-token")
    members: Mapped[list[Member]] = relationship(back_populates="team")


class Member(Base):
    __tablename__ = "members"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    name: Mapped[str] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(default=True)
    team: Mapped[Team] = relationship(back_populates="members")


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, default="user")
    active: Mapped[bool] = mapped_column(default=True)


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def sqlite_foreign_keys(connection, _connection_record):
        connection.execute("PRAGMA foreign_keys = ON")

    Base.metadata.create_all(engine)
    sessionmaker_ = sessionmaker(engine, expire_on_commit=False)
    with sessionmaker_() as session:
        session.add_all([Team(name="Alpha"), Team(name="Beta")])
        session.commit()
        session.add_all([Member(team_id=1, name="Alice"), Member(team_id=1, name="Bob"),
                         Member(team_id=2, name="Charlie")])
        session.add(Account(email="root@example.org", password_hash=hash_password("password123"), role="admin"))
        session.commit()
    yield sessionmaker_
    engine.dispose()


@pytest.fixture
def harness(db):
    app = FastAPI()
    auth = LocalAuth("admin", hash_password("password123"))
    admin = Admin(app, session_factory=db, auth=auth, secret_key="a" * 64, secure_cookie=False)
    admin.add_resource(Resource(Team, search_fields=["name"], fields={"secret_token": Field(visible=False)}))
    admin.add_resource(Resource(Member, search_fields=["name"], list_fields=["id", "name", "team_id"]))
    client = TestClient(app)
    return client, db, admin


def signed_in(client):
    response = client.post("/admin/auth/login", json={"username": "admin", "password": "password123"})
    assert response.status_code == 200, response.text
    return {"X-CSRF-Token": response.json()["csrf"]}


def test_authorization_login_logout_csrf(harness):
    client, _db, _admin = harness
    assert client.get("/admin/api/schema").status_code == 401
    assert client.post("/admin/auth/login", json={"username": "admin", "password": "bad"}).status_code == 401
    assert client.post("/admin/auth/login", json={"username": "admin", "password": "password123"},
                       headers={"Origin": "https://evil.example"}).status_code == 403
    csrf = signed_in(client)
    assert client.get("/admin/auth/me").json()["user"]["username"] == "admin"
    assert client.post("/admin/api/resources/teams", json={"name": "Delta"}).status_code == 403
    assert client.post("/admin/api/resources/teams", json={"name": "Delta"},
                       headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert client.post("/admin/auth/logout", headers=csrf).status_code == 200
    assert client.get("/admin/api/schema").status_code == 401


def test_schema_search_validation_crud(harness):
    client, db, _admin = harness
    csrf = signed_in(client)
    metadata = client.get("/admin/api/schema").json()
    team = next(r for r in metadata["resources"] if r["id"] == "teams")
    assert [f["name"] for f in team["fields"]] == ["id", "name"]
    assert team["primaryKey"] == "id"
    assert client.get("/admin/api/resources/teams?q=Al").json()["total"] == 1
    assert client.get("/admin/api/resources/teams?filter.name=Beta").json()["total"] == 1
    assert client.get("/admin/api/resources/teams?sort=invalid").status_code == 422
    assert client.get("/admin/api/resources/teams?filter.secret_token=private").status_code == 422
    assert client.get("/admin/api/resources/teams?offset=-1").status_code == 422
    assert client.post("/admin/api/resources/teams", json={}, headers=csrf).status_code == 422
    assert client.post("/admin/api/resources/teams", json={"name": "X", "id": 99}, headers=csrf).status_code == 422
    assert client.post("/admin/api/resources/teams", json={"name": "X", "secret_token": "leak"}, headers=csrf).status_code == 422
    response = client.post("/admin/api/resources/teams", json={"name": "Gamma"}, headers=csrf)
    assert response.status_code == 201, response.text
    pk = response.json()["record"]["id"]
    assert "secret_token" not in response.text
    assert client.post("/admin/api/resources/teams", json={"name": "Gamma"}, headers=csrf).status_code == 409
    got = client.get(f"/admin/api/resources/teams/{pk}")
    assert got.json()["record"]["name"] == "Gamma"
    assert client.patch(f"/admin/api/resources/teams/{pk}", json={"name": "Gamma Inc"}, headers=csrf).status_code == 200
    assert client.delete(f"/admin/api/resources/teams/{pk}", headers=csrf).json() == {"ok": True}
    assert client.get(f"/admin/api/resources/teams/{pk}").status_code == 404
    assert client.get("/admin/api/resources/teams?q=%25").json()["total"] == 0


def test_relations_filter_options_and_fk(harness):
    client, _db, _admin = harness
    csrf = signed_in(client)
    metadata = client.get("/admin/api/schema").json()
    member = next(r for r in metadata["resources"] if r["id"] == "members")
    assert next(f for f in member["fields"] if f["name"] == "team_id")["relation"]["resource"] == "teams"
    assert {r["name"] for r in member["relationships"]} == {"team"}
    options = client.get("/admin/api/resources/teams/options?q=Al").json()["items"]
    assert options == [{"value": 1, "label": "Alpha"}]
    related = client.get("/admin/api/resources/teams/1/relationships/members")
    assert related.status_code == 200, related.text
    assert related.json()["total"] == 2
    assert client.get("/admin/api/resources/members?filter.team_id=1").json()["total"] == 2
    created = client.post("/admin/api/resources/members", json={"name": "New", "team_id": 1}, headers=csrf)
    assert created.status_code == 201, created.text
    assert client.get("/admin/api/resources/teams/1/relationships/members").json()["total"] == 3
    assert client.get("/admin/api/resources/teams/1/relationships/invalid").status_code == 404
    related_parent = client.get("/admin/api/resources/members/1/relationships/team")
    assert related_parent.status_code == 200, related_parent.text
    assert related_parent.json()["total"] == 1
    assert related_parent.json()["items"][0]["name"] == "Alpha"
    assert client.post("/admin/api/resources/members", json={"name": "Broken", "team_id": 99}, headers=csrf).status_code == 409
    # FK constraints also block deletion of a referenced parent.
    assert client.delete("/admin/api/resources/teams/1", headers=csrf).status_code == 409


def test_custom_actions_and_permissions(db):
    async def allow(principal, resource, action, record):
        if principal.id == "read-only":
            return action in ("list", "show")
        return True

    async def login(username, password):
        return Principal(id=username, username=username, roles=["viewer"] if username == "read-only" else ["admin"]) if password == "yes" else None

    def rename(record, session, _principal, payload):
        record.name = payload["name"]
        session.commit()
        return {"renamed": record.id}

    app = FastAPI()
    admin = Admin(app, session_factory=db, auth=CallbackAuth(login=login, authorize=allow),
                  secret_key="secret" * 12, secure_cookie=False)
    admin.add_resource(Resource(Team, actions=[Action("rename", rename)]))
    client = TestClient(app)
    assert client.post("/admin/auth/login", json={"username": "read-only", "password": "yes"}).status_code == 200
    meta = client.get("/admin/api/schema").json()["resources"][0]
    assert meta["capabilities"]["edit"] is False
    assert meta["actions"] == []
    assert client.post("/admin/api/resources/teams/1/actions/rename", json={"name": "foo"}).status_code == 403
    signed = client.post("/admin/auth/login", json={"username": "root", "password": "yes"}).json()
    changed = client.post("/admin/api/resources/teams/1/actions/rename", json={"name": "Alpha New"},
                          headers={"X-CSRF-Token": signed["csrf"]})
    assert changed.status_code == 200, changed.text
    assert client.get("/admin/api/resources/teams/1").json()["record"]["name"] == "Alpha New"


def test_scope_restricts_list_detail_and_relations(db):
    def scope(_principal, stmt):
        return stmt.where(Team.name == "Alpha")

    app = FastAPI()
    admin = Admin(app, session_factory=db, auth=LocalAuth("root", hash_password("pw")),
                  secret_key="secret" * 12, secure_cookie=False)
    admin.add_resource(Resource(Team, scope=scope))
    admin.add_resource(Member)
    client = TestClient(app)
    client.post("/admin/auth/login", json={"username": "root", "password": "pw"})
    assert client.get("/admin/api/resources/teams").json()["total"] == 1
    assert client.get("/admin/api/resources/teams/2").status_code == 404
    assert len(client.get("/admin/api/resources/teams/options").json()["items"]) == 1


def test_model_auth_reloads_account(db):
    app = FastAPI()
    auth = ModelAuth(db, Account)
    admin = Admin(app, session_factory=db, auth=auth, secret_key="secret" * 12, secure_cookie=False)
    admin.add_resource(Resource(Team))
    client = TestClient(app)
    response = client.post("/admin/auth/login", json={"username": "root@example.org", "password": "password123"})
    assert response.status_code == 200, response.text
    assert client.get("/admin/api/schema").status_code == 200
    with db() as session:
        user = session.scalar(select(Account).where(Account.email == "root@example.org"))
        user.active = False
        session.commit()
    assert client.get("/admin/api/schema").status_code == 401


def test_hashes_and_static_safety(harness, tmp_path, monkeypatch):
    client, _db, admin = harness
    monkeypatch.setattr(admin, "dist_dir", tmp_path)
    assert verify_password("abc", hash_password("abc"))
    assert not verify_password("wrong", hash_password("abc"))
    assert not verify_password("abc", "not-a-hash")
    assert client.get("/admin/").status_code == 503
    assert client.get("/admin/favicon.svg").status_code == 503
    assert client.get("/admin/assets/not-found.js").status_code == 503


def test_served_spa_and_unknown_assets(db, tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html><body>SPA</body></html>")
    (dist / "assets" / "app.js").write_text("console.log('ok')")
    app = FastAPI()
    Admin(app, session_factory=db, auth=LocalAuth("root", hash_password("pw")),
          secret_key="secret" * 12, secure_cookie=False, dist_dir=dist)
    client = TestClient(app)
    assert client.get("/admin/").text.find("SPA") >= 0
    assert client.get("/admin/resources/teams/1").status_code == 200
    assert client.get("/admin/assets/app.js").status_code == 200
    assert client.get("/admin/assets/not-found.js").status_code == 404
    assert client.get("/admin/favicon.svg").status_code == 404


def test_unicode_local_auth_and_streaming_json_limit():
    app = FastAPI()
    Admin(app, session_factory=lambda: None, auth=LocalAuth("André", hash_password("sample")),
          secret_key="x" * 64, secure_cookie=False, max_json_bytes=96)
    with TestClient(app) as client:
        assert client.post("/admin/auth/login", json={"username": "André", "password": "sample"}).status_code == 200
        chunks = iter((b'{"username":"demo","password":"', b'x' * 128, b'"}'))
        rejected = client.post("/admin/auth/login", content=chunks)
        assert rejected.status_code == 413
