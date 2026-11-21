"""v0.4 metadata, typed label, relationship and query semantics."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import ForeignKey, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import StaticPool

from pyntral import Admin, CallbackAuth, Field, Principal, Relationship, Resource


class Base(DeclarativeBase):
    pass


class Team(Base):
    __tablename__ = "v04_teams"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    members: Mapped[list[Member]] = relationship(back_populates="team")


class Member(Base):
    __tablename__ = "v04_members"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("v04_teams.id"))
    name: Mapped[str] = mapped_column(String(120))
    team: Mapped[Team] = relationship(back_populates="members")


@pytest.fixture
def panel():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def fk_on(dbapi, _record):
        dbapi.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions() as session:
        session.add_all([Team(name="Engineering"), Team(name="Operations")])
        session.flush()
        session.add_all([Member(team_id=1, name="Alice"), Member(team_id=1, name="Bob"),
                         Member(team_id=2, name="Carol")])
        session.commit()

    async def login(username, password):
        return Principal(id="1", username="admin", roles=["admin"]) if password == "password" else None

    app = FastAPI()
    admin = Admin(app, session_factory=sessions, auth=CallbackAuth(login),
                  secret_key="very-secret-key" * 4, secure_cookie=False)
    admin.add_resource(Resource(Team, visible_name=Team.name,
                                relationships={"members": Relationship(label="Team members", selectable=True)},
                                form_layout="stack", detail_layout="stack"))
    admin.add_resource(Resource(Member, visible_name=Member.name,
                                relationships={"team": Relationship(visible=False)},
                                fields={"name": Field(span=2)}, search_fields=["name"],
                                label_factory=lambda member: f"{member.name} (#{member.id})"))
    with TestClient(app) as client:
        assert client.post("/admin/auth/login", json={"username": "admin", "password": "password"}).status_code == 200
        yield client, admin
    engine.dispose()


def test_metadata_layout_selectable_reverse_hidden(panel):
    client, _ = panel
    data = client.get("/admin/api/schema").json()
    team = next(r for r in data["resources"] if r["id"] == "teams")
    member = next(r for r in data["resources"] if r["id"] == "members")
    assert team["titleField"] == "name"
    assert team["formLayout"] == "stack" and team["detailLayout"] == "stack"
    assert team["relationships"] == [{"name": "members", "resource": "members", "many": True,
                                      "label": "Team members", "selectable": True, "layout": "table"}]
    assert member["relationships"] == []
    assert next(f for f in member["fields"] if f["name"] == "name")["span"] == 2
    assert client.get("/admin/api/resources/members/1/relationships/team").status_code == 404


def test_search_options_selected_ids_labels(panel):
    client, _ = panel
    assert client.get("/admin/api/resources/members/options?q=ali").json()["items"] == [
        {"value": 1, "label": "Alice (#1)"}
    ]
    assert client.get("/admin/api/resources/members/options?ids=3,1").json()["items"] == [
        {"value": 1, "label": "Alice (#1)"}, {"value": 3, "label": "Carol (#3)"}
    ]
    assert client.get("/admin/api/resources/members/options?q=%25").json()["items"] == []
    assert client.get("/admin/api/resources/members/options?ids=bad").status_code == 422


def test_related_search_scoping_and_reverse(panel):
    client, _ = panel
    base = "/admin/api/resources/teams/1/relationships/members"
    all_items = client.get(base).json()
    assert all_items["total"] == 2
    assert [item["name"] for item in client.get(base + "?q=ali").json()["items"]] == ["Alice"]
    assert client.get(base + "?q=car").json()["total"] == 0
    assert client.get(base + "?q=%25").json()["total"] == 0


def test_visible_name_rejects_relationship_and_foreign_model():
    with pytest.raises(ValueError, match="visible_name"):
        from pyntral.orm import MapperAdapter
        MapperAdapter(Resource(Member, visible_name=Member.team))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="visible_name"):
        MapperAdapter(Resource(Member, visible_name=Team.name))
    with pytest.raises(ValueError, match="relationship"):
        MapperAdapter(Resource(Member, relationships={"missing": Relationship()}))
    with pytest.raises(ValueError, match="Layout"):
        Resource(Member, form_layout="zigzag")
    with pytest.raises(ValueError, match="Field.span"):
        Field(span=3)
