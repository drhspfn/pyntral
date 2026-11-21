"""Black-box coverage of v0.6 typed filters and metadata permissions."""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from enum import Enum

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Date, Enum as SqlEnum, ForeignKey, Numeric, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import StaticPool

from pyntral import Admin, Field, LocalAuth, Resource, hash_password


class Base(DeclarativeBase):
    pass


class State(str, Enum):
    pending = "pending"
    fulfilled = "fulfilled"
    cancelled = "cancelled"


class Group(Base):
    __tablename__ = "v06_groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    rows: Mapped[list[Row]] = relationship(back_populates="group")


class Row(Base):
    __tablename__ = "v06_rows"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("v06_groups.id"))
    name: Mapped[str] = mapped_column(String(60))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    active: Mapped[bool] = mapped_column(default=True)
    state: Mapped[State] = mapped_column(SqlEnum(State))
    created: Mapped[date] = mapped_column(Date)
    group: Mapped[Group] = relationship(back_populates="rows")


@pytest.fixture
def admin_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def fk_on(connection, _rec):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as session:
        session.add_all([Group(id=1, name="One"), Group(id=2, name="Two")])
        session.add_all([
            Row(id=1, group_id=1, name="Al%pha", amount=Decimal("10.50"), active=True,
                state=State.pending, created=date(2026, 1, 5)),
            Row(id=2, group_id=1, name="alpha_foo", amount=Decimal("20.00"), active=False,
                state=State.fulfilled, created=date(2026, 2, 10)),
            Row(id=3, group_id=2, name="Bravo", amount=Decimal("30.75"), active=True,
                state=State.cancelled, created=date(2026, 3, 15)),
            Row(id=4, group_id=2, name="Gamma", amount=Decimal("40.00"), active=True,
                state=State.fulfilled, created=date(2026, 4, 20)),
        ])
        session.commit()
    app = FastAPI()
    admin = Admin(app, session_factory=factory, auth=LocalAuth("admin", hash_password("pass")),
                  secret_key="s" * 64, secure_cookie=False)
    admin.add_resource(Resource(Group))
    admin.add_resource(Resource(Row, search_fields=["name"], fields={
        "name": Field(filter_operators=["eq", "contains", "starts_with", "ends_with"],
                      filter_width=245),
    }))
    client = TestClient(app)
    response = client.post("/admin/auth/login", json={"username": "admin", "password": "pass"})
    assert response.status_code == 200
    yield client
    client.close()
    engine.dispose()


def fetch(client: TestClient, **filters: str) -> list[int]:
    response = client.get("/admin/api/resources/rows", params=filters)
    assert response.status_code == 200, response.text
    return sorted(item["id"] for item in response.json()["items"])


def test_numeric_operators_ranges_and_shorthand_equality(admin_client):
    client = admin_client
    assert fetch(client, **{"filter.amount.gt": "20"}) == [3, 4]
    assert fetch(client, **{"filter.amount.gte": "20"}) == [2, 3, 4]
    assert fetch(client, **{"filter.amount.lt": "30.75"}) == [1, 2]
    assert fetch(client, **{"filter.amount.lte": "30.75"}) == [1, 2, 3]
    assert fetch(client, **{"filter.id.neq": "1"}) == [2, 3, 4]
    assert fetch(client, **{"filter.id": "2"}) == [2]
    assert fetch(client, **{"filter.amount.between": json.dumps({"from": 15, "to": 31})}) == [2, 3]
    assert fetch(client, **{"filter.id.between": json.dumps({"from": 2, "to": 3})}) == [2, 3]


def test_case_insensitive_literal_like_patterns(admin_client):
    client = admin_client
    assert fetch(client, **{"filter.name.contains": "AL"}) == [1, 2]
    assert fetch(client, **{"filter.name.contains": "%"}) == [1]
    assert fetch(client, **{"filter.name.contains": "_"}) == [2]
    assert fetch(client, **{"filter.name.starts_with": "Al%"}) == [1]
    assert fetch(client, **{"filter.name.ends_with": "foo"}) == [2]
    assert fetch(client, **{"filter.name.eq": "AL%PHA"}) == []  # Equality remains case sensitive


def test_enum_include_and_exclude_with_boolean_and_foreign_key(admin_client):
    client = admin_client
    assert fetch(client, **{"filter.state.in": json.dumps(["pending", "fulfilled"])}) == [1, 2, 4]
    assert fetch(client, **{"filter.state.not_in": json.dumps(["cancelled"])}) == [1, 2, 4]
    assert fetch(client, **{
        "filter.state.in": json.dumps(["pending", "fulfilled"]),
        "filter.state.not_in": json.dumps(["cancelled"]),
    }) == [1, 2, 4]
    bad = client.get("/admin/api/resources/rows", params={
        "filter.state.in": json.dumps(["pending", "fulfilled"]),
        "filter.state.not_in": json.dumps(["fulfilled"]),
    })
    assert bad.status_code == 422
    assert fetch(client, **{"filter.group_id.eq": "1"}) == [1, 2]
    assert fetch(client, **{"filter.active.eq": "false"}) == [2]
    assert fetch(client, **{"filter.active.eq": "true", "filter.state.not_in": '["cancelled"]'}) == [1, 4]


def test_date_ranges(admin_client):
    client = admin_client
    assert fetch(client, **{"filter.created.between": '{"from":"2026-02-01","to":"2026-03-31"}'}) == [2, 3]
    assert fetch(client, **{"filter.created.lt": "2026-03-15"}) == [1, 2]
    assert fetch(client, **{"filter.created.gte": "2026-03-15"}) == [3, 4]


@pytest.mark.parametrize("params", [
    {"filter.name.gt": "1"},
    {"filter.active.between": '{"from":false,"to":true}'},
    {"filter.name.unknown": "X"},
    {"filter.name.not_in": '["A"]'},
    {"filter.name...": "test"},
    {"filter.id.between": '{"from":3}'},
    {"filter.id.between": '{"from":3,"to":1}'},
    {"filter.amount.between": '{"from":"abc","to":40}'},
    {"filter.amount.gt": "NaN"},
    {"filter.amount.lt": "Infinity"},
    {"filter.created.between": "bogus"},
    {"filter.state.in": "null"},
    {"filter.state.in": "[]"},
    {"filter.state.in": '["unknown"]'},
    {"filter.state.in": '["pending",{}]'},
    {"filter.unknown.eq": "1"},
])
def test_invalid_filter_is_rejected(admin_client, params):
    response = admin_client.get("/admin/api/resources/rows", params=params)
    assert response.status_code == 422, response.text


def test_duplicate_filter_parameter_rejected(admin_client):
    response = admin_client.get("/admin/api/resources/rows?filter.id.eq=1&filter.id.eq=2")
    assert response.status_code == 422


def test_filter_metadata_and_opt_in_quick_search(admin_client):
    resources = admin_client.get("/admin/api/schema").json()["resources"]
    row = next(item for item in resources if item["id"] == "rows")
    kinds = {field["name"]: field for field in row["fields"]}
    assert row["showSearch"] is False
    assert kinds["id"]["kind"] == "integer"
    assert "between" in kinds["amount"]["filterOperators"]
    assert kinds["group_id"]["filterOperators"] == ["eq", "neq"]
    assert kinds["active"]["filterOperators"] == ["eq"]
    assert "in" in kinds["state"]["filterOperators"]
    assert "contains" in kinds["name"]["filterOperators"]
    assert "neq" not in kinds["name"]["filterOperators"]
    assert kinds["name"]["maxLength"] == 60
    assert kinds["name"]["filterWidth"] == 245
    assert kinds["amount"]["precision"] == 10
    assert kinds["amount"]["scale"] == 2
    assert kinds["id"]["maxLength"] is None


def test_filter_width_bounds():
    with pytest.raises(ValueError, match="filter_width"):
        Field(filter_width=100)
    with pytest.raises(ValueError, match="filter_width"):
        Field(filter_width=600)
    with pytest.raises(ValueError, match="filter_width"):
        Field(filter_width=True)
    assert Field(filter_width=160).filter_width == 160


def test_invalid_field_filter_configuration():
    with pytest.raises(ValueError, match="Unsupported filter operator"):
        from pyntral.orm import MapperAdapter
        MapperAdapter(Resource(Row, fields={"active": Field(filter_operators=["contains"])}))


def test_foreign_key_does_not_accept_numeric_range(admin_client):
    response = admin_client.get("/admin/api/resources/rows", params={
        "filter.group_id.between": '{"from":1,"to":2}'
    })
    assert response.status_code == 422
