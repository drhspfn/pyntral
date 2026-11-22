"""Conditional fields remain protected in lists, record views and mutations."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import ForeignKey, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import StaticPool
from pyntral import Admin, CallbackAuth, Field, Principal, Resource


class Base(DeclarativeBase):
    pass


class Folder(Base):
    __tablename__ = "conditional_folders"
    id: Mapped[int] = mapped_column(primary_key=True)
    notes: Mapped[list["Note"]] = relationship(back_populates="folder")


class Note(Base):
    __tablename__ = "conditional_notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(100))
    body: Mapped[str] = mapped_column(String(100))
    folder_id: Mapped[int] = mapped_column(ForeignKey("conditional_folders.id"))
    folder: Mapped[Folder] = relationship(back_populates="notes")


class Bookmark(Base):
    __tablename__ = "conditional_bookmarks"
    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("conditional_notes.id"))
    note: Mapped[Note] = relationship()
    title: Mapped[str]


def test_conditional_fields_and_row_actions():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions() as db:
        db.add(Folder(notes=[
            Note(owner="alice", title="A", body="Alice's note"),
            Note(owner="bob", title="B", body="Bob's note"),
        ]))
        db.commit()
    async def login(username, _password):
        return Principal(id=username, username=username, roles=["viewer"])
    app=FastAPI()
    admin=Admin(app, session_factory=sessions, auth=CallbackAuth(login), secret_key="k"*64, secure_cookie=False)
    admin.add_resource(Resource(Folder))
    admin.add_resource(Resource(Bookmark))
    admin.add_resource(Resource(
        Note, title_field="body", search_fields=["title", "body"],
        fields={"body": Field(read_when=lambda p, r: p.id == r.owner,
                              write_when=lambda p, r: p.id == r.owner)},
        operation_policy=lambda p, action, row: row is None or (
            (action != "select" or row.title == "A") and
            (action not in ("edit", "delete") or p.id == row.owner)
        ),
    ))
    with TestClient(app) as c:
        csrf=c.post("/admin/auth/login",json={"username":"alice","password":"x"}).json()["csrf"]
        listing=c.get("/admin/api/resources/notes").json()["items"]
        assert listing[0]["body"] == "Alice's note"
        assert "body" not in listing[1]
        assert "body" not in c.get("/admin/api/resources/notes/2").json()["record"]
        assert c.get("/admin/api/resources/notes?filter.body.eq=private").status_code==422
        assert c.get("/admin/api/resources/notes?sort=body").status_code==422
        assert c.patch("/admin/api/resources/notes/2",json={"body":"stolen"},headers={"X-CSRF-Token":csrf}).status_code==403
        assert c.patch("/admin/api/resources/notes/1",json={"body":"updated"},headers={"X-CSRF-Token":csrf}).status_code==200

        notes = "/admin/api/resources/notes"
        assert c.get(notes, params={"q": "Bob's note"}).json()["items"] == []
        assert c.get(notes, params={"q": "B"}).json()["total"] == 1
        assert c.get(f"{notes}/export", params={"q": "Bob's note", "format": "json"}).json() == []
        related = "/admin/api/resources/folders/1/relationships/notes"
        assert c.get(related, params={"q": "Bob's note"}).json()["items"] == []
        assert c.get(related, params={"q": "B"}).json()["total"] == 1
        assert c.get(f"{notes}/options", params={"ids": "1,2"}).json()["items"] == [
            {"value": 1, "label": "updated"},
        ]
        assert c.get(f"{notes}/options", params={"q": "updated"}).json()["items"] == []
        h = {"X-CSRF-Token": csrf}
        bookmarks = "/admin/api/resources/bookmarks"
        assert c.post(bookmarks, json={"note_id": 1, "title": "My note"}, headers=h).status_code == 201
        assert c.post(bookmarks, json={"note_id": 2, "title": "Unavailable"}, headers=h).status_code == 409

        c.post("/admin/auth/login", json={"username": "bob", "password": "x"})
        assert c.get(f"{notes}/options").json()["items"] == [{"value": 1, "label": "1"}]
    engine.dispose()
