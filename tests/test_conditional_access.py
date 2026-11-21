"""Conditional fields remain protected in lists, record views and mutations."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool
from pyntral import Admin, CallbackAuth, Field, Principal, Resource


class Base(DeclarativeBase):
    pass


class Note(Base):
    __tablename__ = "conditional_notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(100))
    body: Mapped[str] = mapped_column(String(100))


def test_conditional_fields_and_row_actions():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions() as db:
        db.add_all([Note(owner="alice", title="A", body="private A"),
                    Note(owner="bob", title="B", body="private B")])
        db.commit()
    async def login(username, _password):
        return Principal(id=username, username=username, roles=["viewer"])
    app=FastAPI()
    admin=Admin(app, session_factory=sessions, auth=CallbackAuth(login), secret_key="k"*64, secure_cookie=False)
    admin.add_resource(Resource(Note,
        fields={"body": Field(read_when=lambda p,r:p.id==r.owner,
                                write_when=lambda p,r:p.id==r.owner)},
        operation_policy=lambda p,action,record: record is None or action not in ("edit", "delete") or p.id==record.owner))
    with TestClient(app) as c:
        csrf=c.post("/admin/auth/login",json={"username":"alice","password":"x"}).json()["csrf"]
        listing=c.get("/admin/api/resources/notes").json()["items"]
        assert listing[0]["body"]=="private A"
        assert "body" not in listing[1]
        assert "body" not in c.get("/admin/api/resources/notes/2").json()["record"]
        assert c.get("/admin/api/resources/notes?filter.body.eq=private").status_code==422
        assert c.get("/admin/api/resources/notes?sort=body").status_code==422
        assert c.patch("/admin/api/resources/notes/2",json={"body":"stolen"},headers={"X-CSRF-Token":csrf}).status_code==403
        assert c.patch("/admin/api/resources/notes/1",json={"body":"updated"},headers={"X-CSRF-Token":csrf}).status_code==200
    engine.dispose()
