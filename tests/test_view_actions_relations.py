"""Regression tests for per-screen fields, collection actions and editable M:N."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Column, ForeignKey, String, Table, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import StaticPool

from pyntral import Action, Admin, CallbackAuth, Field, FieldView, Principal, Resource


class Base(DeclarativeBase):
    pass


link_table = Table(
    "feature_people_labels", Base.metadata,
    Column("person_id", ForeignKey("feature_people.id"), primary_key=True),
    Column("label_id", ForeignKey("feature_labels.id"), primary_key=True),
)


class Person(Base):
    __tablename__ = "feature_people"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    note: Mapped[str] = mapped_column(String(100), default="private")
    labels: Mapped[list[Label]] = relationship(secondary=link_table, back_populates="people")


class Label(Base):
    __tablename__ = "feature_labels"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    people: Mapped[list[Person]] = relationship(secondary=link_table, back_populates="labels")


def setup(permission=None):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions() as session:
        session.add_all([Person(name="Alice"), Person(name="Bob"), Label(name="Important"), Label(name="VIP")])
        session.commit()

    async def login(_username: str, _password: str):
        return Principal(id="admin", username="admin", roles=["admin"])

    async def authorize(principal, resource, action, record=None):
        if permission is not None:
            return permission(resource, action, record)
        return True

    app = FastAPI()
    panel = Admin(app, session_factory=sessions, auth=CallbackAuth(login, authorize=authorize),
                  secret_key="a" * 64, secure_cookie=False)
    panel.add_resource(Resource(
        Person, fields={
            "name": Field(
                list=FieldView(order=5), show=FieldView(order=2),
                edit=FieldView(readonly=True),
                filter=FieldView(visible=False),
            ),
            "note": Field(list=FieldView(visible=False), show=FieldView(visible=False),
                          create=FieldView(visible=False)),
        },
        crud_views={"list": "people-list", "edit": "people-editor"},
        actions=[
            Action("mass_flag", lambda records, session, principal, payload: [r.id for r in records],
                   kind="bulk", label="Flag selected"),
            Action("count_people", lambda session, principal, payload: session.query(Person).count(),
                   kind="resource", label="Count"),
            Action("rename", lambda record, session, principal, payload: record.name,
                   kind="record", label="Rename"),
        ],
    ))
    panel.add_resource(Resource(Label, search_fields=["name"], visible_name=Label.name))
    client = TestClient(app)
    login_response = client.post("/admin/auth/login", json={"username": "admin", "password": "password"})
    assert login_response.status_code == 200
    csrf = {"X-CSRF-Token": login_response.json()["csrf"]}
    return client, sessions, csrf, engine


def test_contextual_fields_and_crud_schema():
    client, sessions, csrf, engine = setup()
    try:
        info = client.get("/admin/api/schema").json()
        res = next(r for r in info["resources"] if r["id"] == "persons")
        assert res["crudViews"] == {"list": "people-list", "edit": "people-editor"}
        fields = {field["name"]: field for field in res["fields"]}
        assert fields["note"]["views"]["list"]["visible"] is False
        assert fields["name"]["views"]["edit"]["readonly"] is True
        assert fields["name"]["views"]["filter"]["visible"] is False
        assert "note" not in client.get("/admin/api/resources/persons").text
        assert "note" not in client.get("/admin/api/resources/persons/1").text
        assert client.get("/admin/api/resources/persons?filter.name.eq=Alice").status_code == 422
        assert client.patch("/admin/api/resources/persons/1", json={"name": "No"}, headers=csrf).status_code == 403
        assert client.post("/admin/api/resources/persons", json={"name": "Yes", "note": "leak"}, headers=csrf).status_code == 403
        assert client.post("/admin/api/resources/persons", json={"name": "Yes"}, headers=csrf).status_code == 201
    finally:
        client.close()
        engine.dispose()


def test_resource_and_bulk_actions_reject_invalid_and_unscoped_records():
    client, sessions, csrf, engine = setup()
    try:
        schema = client.get("/admin/api/schema").json()
        actions = next(r for r in schema["resources"] if r["id"] == "persons")["actions"]
        assert {a["kind"] for a in actions} == {"record", "resource", "bulk"}
        url = "/admin/api/resources/persons/actions/"
        assert client.post(url + "count_people", json={}, headers=csrf).json()["result"] == 2
        assert client.post(url + "mass_flag", json={"ids": [2, 1]}, headers=csrf).json()["result"] == [2, 1]
        for bad in ([], [1, 1], [1, 99], [True], [0] * 101):
            assert client.post(url + "mass_flag", json={"ids": bad}, headers=csrf).status_code in (404, 422)
        assert client.post(url + "rename", json={}, headers=csrf).status_code == 404
        assert client.post(url + "count_people", json={}).status_code == 403
        assert client.post("/admin/api/resources/persons/1/actions/mass_flag", json={}, headers=csrf).status_code == 403
    finally:
        client.close()
        engine.dispose()


def test_many_to_many_attach_detach_create_atomic():
    client, sessions, csrf, engine = setup()
    base = "/admin/api/resources/persons/1/relationships/labels"
    try:
        data = client.get("/admin/api/schema").json()
        rel = next(r for r in data["resources"] if r["id"] == "persons")["relationships"][0]
        assert rel["editable"] is True
        assert client.post(base + "/attach", json={"id": 1}).status_code == 403
        assert client.post(base + "/attach", json={"id": 1}, headers=csrf).status_code == 200
        assert client.post(base + "/attach", json={"id": 1}, headers=csrf).status_code == 200
        assert client.get(base).json()["total"] == 1
        assert client.post(base + "/detach", json={"id": 2}, headers=csrf).status_code == 404
        assert client.post(base + "/detach", json={"id": 1}, headers=csrf).status_code == 200
        assert client.get(base).json()["total"] == 0
        # Unlink never deletes the target entity.
        assert client.get("/admin/api/resources/labels/1").status_code == 200
        made = client.post(base + "/create", json={"name": "New label"}, headers=csrf)
        assert made.status_code == 201, made.text
        assert client.get(base).json()["total"] == 1
        assert made.json()["record"]["name"] == "New label"
        assert client.post(base + "/create", json={"name": "Important"}, headers=csrf).status_code == 409
        assert client.get(base).json()["total"] == 1
        assert client.post(base + "/attach", json={"id": "bad"}, headers=csrf).status_code == 422
    finally:
        client.close()
        engine.dispose()


def test_many_to_many_enforces_target_scope_and_parent_edit():
    def permissions(resource, action, record):
        if resource == "persons" and action == "edit":
            return False
        return True
    client, sessions, csrf, engine = setup(permissions)
    try:
        base = "/admin/api/resources/persons/1/relationships/labels"
        assert client.post(base + "/attach", json={"id": 1}, headers=csrf).status_code == 403
        assert client.post(base + "/create", json={"name": "Unwanted"}, headers=csrf).status_code == 403
        assert client.get("/admin/api/resources/labels?filter.name.eq=Unwanted").json()["total"] == 0
    finally:
        client.close()
        engine.dispose()
