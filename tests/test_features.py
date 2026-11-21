"""Navigation, contextual actions, and Pydantic RPC integration tests."""
from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import ForeignKey, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import StaticPool

from pyntral import (
    Action, Admin, Bridge, CallbackAuth, Field, NavigationGroup, Page, Principal, Resource,
)
from pyntral.typegen import render_bridge_types


class Base(DeclarativeBase):
    pass


class Agent(Base):
    __tablename__ = "test_agents"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(90))
    enabled: Mapped[bool] = mapped_column(default=True)
    runs: Mapped[list[Run]] = relationship(back_populates="agent")


class Run(Base):
    __tablename__ = "test_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("test_agents.id"), nullable=False)
    agent: Mapped[Agent] = relationship(back_populates="runs")


class UrlInput(BaseModel):
    asset_id: int


class UrlOutput(BaseModel):
    url: str
    metadata: dict[str, str] | None = None


@pytest.fixture
def app_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def foreign_keys(dbapi, _record):
        dbapi.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions() as session:
        session.add_all([Agent(name="Alpha", enabled=True), Agent(name="Beta", enabled=False)])
        session.commit()
        session.add(Run(agent_id=1))
        session.commit()

    async def login(username: str, password: str):
        if password == "pass":
            return Principal(id=username, username=username, roles=[username])
        return None

    async def authorize(principal, resource, action, record=None):
        if principal.id == "viewer":
            return not (action.startswith("action:") or resource.startswith("bridge:"))
        return True

    def disable(record, session, _principal, _payload):
        record.enabled = False
        session.commit()
        return {"ok": True}

    async def preview_url(payload: UrlInput, ctx: Any) -> UrlOutput:
        return UrlOutput(url=f"https://cdn.example.test/assets/{payload.asset_id}.png",
                         metadata={"viewer": ctx.principal.id})

    app = FastAPI()
    admin = Admin(app, session_factory=sessions, auth=CallbackAuth(login, authorize=authorize),
                  secret_key="test" * 16, secure_cookie=False,
                  default_theme="dark", animations=False,
                  theme={"dark": {"primary": "#abcd12", "custom-width": "50px"}})
    admin.add_group(NavigationGroup("Agents", icon="bot", order=1))
    admin.add_group(NavigationGroup("Agents/Runs", icon="cpu"))
    admin.add_resource(Resource(Agent, navigation="Agents", actions=[
        Action("disable", disable, position="row", appearance="badge", dialog="disable-preview",
               visible=lambda _principal, record: record.enabled),
        Action("preview", lambda *_: {}, component="preview", position="detail"),
    ]))
    admin.add_resource(Resource(Run, navigation="Agents/Runs"))
    admin.add_page(Page("overview", "Overview", "overview", navigation="Agents"))
    admin.add_bridge(Bridge("asset-url", UrlInput, UrlOutput, preview_url))
    with TestClient(app) as client:
        yield client, admin
    engine.dispose()


def login(client: TestClient, username: str = "admin") -> dict[str, str]:
    response = client.post("/admin/auth/login", json={"username": username, "password": "pass"})
    assert response.status_code == 200, response.text
    return {"X-CSRF-Token": response.json()["csrf"]}


def test_groups_and_theme_contract(app_client):
    client, admin = app_client
    login(client)
    schema = client.get("/admin/api/schema").json()
    assert schema["navigation"]["groups"][1]["path"] == "Agents/Runs"
    assert next(r for r in schema["resources"] if r["id"] == "agents")["navigation"] == "Agents"
    assert next(p for p in schema["pages"] if p["name"] == "overview")["navigation"] == "Agents"
    assert next(r for r in schema["resources"] if r["id"] == "agents")["actions"][0]["dialog"] == "disable-preview"
    assert schema["theme"]["default"] == "dark"
    assert schema["theme"]["animations"] is False
    assert schema["theme"]["tokens"]["dark"]["custom-width"] == "50px"
    with pytest.raises(ValueError, match="Navigation"):
        admin.add_resource(Resource(Agent, navigation="Agents//Bad"))
    with pytest.raises(ValueError, match="Duplicate"):
        admin.add_group(NavigationGroup("Agents"))


def test_context_actions_are_server_guarded(app_client):
    client, _admin = app_client
    csrf = login(client)
    items = client.get("/admin/api/resources/agents").json()
    assert items["actionsByRecord"]["1"] == ["disable", "preview"]
    assert items["actionsByRecord"]["2"] == ["preview"]
    assert client.get("/admin/api/resources/agents/2").json()["actions"] == ["preview"]
    blocked = client.post("/admin/api/resources/agents/2/actions/disable", json={}, headers=csrf)
    assert blocked.status_code == 403
    success = client.post("/admin/api/resources/agents/1/actions/disable", json={}, headers=csrf)
    assert success.status_code == 200, success.text
    assert client.get("/admin/api/resources/agents/1").json()["actions"] == ["preview"]
    assert client.post("/admin/api/resources/agents/1/actions/disable", json={}, headers=csrf).status_code == 403
    login(client, "viewer")
    assert client.get("/admin/api/schema").json()["resources"][0]["actions"] == []
    assert client.get("/admin/api/resources/agents").json()["actionsByRecord"]["1"] == []


def test_bridge_validation_auth_types(app_client):
    client, admin = app_client
    assert client.post("/admin/api/bridge/asset-url", json={"asset_id": 1}).status_code == 401
    csrf = login(client)
    assert client.post("/admin/api/bridge/asset-url", json={"asset_id": 1}).status_code == 403
    invalid = client.post("/admin/api/bridge/asset-url", json={"asset_id": "bad"}, headers=csrf)
    assert invalid.status_code == 422 and invalid.json()["error"]["code"] == "validation_error"
    assert "bad" not in invalid.text  # sensitive raw input is not echoed
    output = client.post("/admin/api/bridge/asset-url", json={"asset_id": 6}, headers=csrf)
    assert output.json()["result"] == {"url": "https://cdn.example.test/assets/6.png",
                                       "metadata": {"viewer": "admin"}}
    code = render_bridge_types(admin.bridges)
    assert 'export type AssetUrlInput = { "asset_id" : number }' in code
    assert 'export async function assetUrl(input: AssetUrlInput)' in code
    assert 'invokeBridge<AssetUrlInput, AssetUrlOutput>("asset-url", input)' in code
    login(client, "viewer")
    assert client.get("/admin/api/schema").json()["bridges"] == []
    assert client.post("/admin/api/bridge/asset-url", json={"asset_id": 1},
                       headers={"X-CSRF-Token": client.get("/admin/auth/me").json()["csrf"]}).status_code == 403


def test_fk_delete_stays_restrictive(app_client):
    client, _admin = app_client
    csrf = login(client)
    error = client.delete("/admin/api/resources/agents/1", headers=csrf)
    assert error.status_code == 409
    assert "referenced" in error.json()["error"]["message"]
    assert client.delete("/admin/api/resources/agents/2", headers=csrf).status_code == 200


def test_bridge_config_validated():
    with pytest.raises(ValueError, match="slug"):
        Bridge("../invalid", UrlInput, UrlOutput, lambda *_: None)
    with pytest.raises(TypeError, match="Pydantic"):
        Bridge("bad-input", dict, UrlOutput, lambda *_: None)
