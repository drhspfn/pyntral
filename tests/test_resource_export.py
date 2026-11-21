"""Safe, filtered exports without write-side effects."""
import csv
import io
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from pyntral import Admin, CallbackAuth, Field, Principal, Resource


class Base(DeclarativeBase):
    pass


class ExportItem(Base):
    __tablename__ = "export_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    internal: Mapped[str] = mapped_column(String(100))


def test_export_respects_range_columns_and_permissions():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions() as session:
        session.add_all([
            ExportItem(id=1, title="=IMPORT(1)", internal="classified"),
            ExportItem(id=2, title="Safe", internal="classified"),
        ])
        session.commit()

    async def login(username, password):
        return Principal(id="tester", username="tester", roles=["admin"])

    app = FastAPI()
    admin = Admin(app, session_factory=sessions, auth=CallbackAuth(login),
                  secret_key="s" * 64, secure_cookie=False)
    admin.add_resource(Resource(ExportItem, list_fields=["id", "title"],
                                fields={"internal": Field(visible=False)}))
    with TestClient(app) as client:
        assert client.post("/admin/auth/login", json={"username": "tester", "password": "x"}).status_code == 200
        path = "/admin/api/resources/export-items/export"
        response = client.get(path, params={"format": "csv", "sort": "id", "desc": "false"})
        assert response.status_code == 200, response.text
        records = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
        assert list(records[0]) == ["id", "title"]
        assert records[0]["title"] == "'=IMPORT(1)"
        assert len(records) == 2
        assert response.headers["X-Export-Rows"] == "2"
        page = client.get(path, params={"format": "json", "offset": 1, "limit": 1, "columns": "title"})
        assert page.status_code == 200
        assert json.loads(page.text) == [{"title": "Safe"}]
        assert client.get(path, params={"columns": "internal"}).status_code == 422
        assert client.get(path, params={"limit": 10001}).status_code == 422
        assert client.get(path, params={"offset": -1}).status_code == 422
    engine.dispose()
