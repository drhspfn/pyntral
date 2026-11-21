from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.pool import StaticPool
import pytest
from pyntral import Admin, CallbackAuth, Principal, Resource

class Base(DeclarativeBase): pass
class Draft(Base):
    __tablename__="concurrency_drafts"
    id: Mapped[int]=mapped_column(primary_key=True)
    title: Mapped[str]=mapped_column(String(80))
    version: Mapped[int]=mapped_column(default=1,nullable=False)
    __mapper_args__={"version_id_col":version}

def test_stale_updates_and_deletes_are_rejected():
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(engine); sf=sessionmaker(engine,expire_on_commit=False)
    async def login(u,p):return Principal(id="u",username="u",roles=["admin"])
    app=FastAPI(); admin=Admin(app,session_factory=sf,auth=CallbackAuth(login),secret_key="x"*64,secure_cookie=False)
    admin.add_resource(Resource(Draft,version_field="version"))
    with TestClient(app) as c:
        csrf=c.post("/admin/auth/login",json={"username":"u","password":"x"}).json()["csrf"]
        headers={"X-CSRF-Token":csrf}
        created=c.post("/admin/api/resources/drafts",headers=headers,json={"title":"Old"})
        assert created.status_code==201,created.text
        pk=created.json()["record"]["id"]
        url=f"/admin/api/resources/drafts/{pk}"
        first=c.get(url).json()["record"]
        assert first["version"]==1
        assert c.patch(url,headers=headers,json={"title":"Missing version"}).status_code==428
        valid={**headers,"If-Match":str(first["version"])}
        assert c.patch(url,headers=valid,json={"title":"New"}).status_code==200
        assert c.patch(url,headers=valid,json={"title":"Stale"}).status_code==412
        assert c.delete(url,headers=valid).status_code==412
        assert c.get(url).json()["record"]["title"]=="New"
        new_ver=c.get(url).json()["record"]["version"]
        assert new_ver==2
        assert c.delete(url,headers={**headers,"If-Match":str(new_ver)}).status_code==200
    engine.dispose()

def test_commit_time_version_race_is_a_precondition_failure():
    from pyntral.orm import MapperAdapter, AdminError
    from unittest.mock import AsyncMock
    import asyncio
    adapter = MapperAdapter(Resource(Draft, version_field="version"))
    session = type("RaceSession", (), {})()
    session.commit = AsyncMock(side_effect=StaleDataError("UPDATE affected zero rows"))
    session.rollback = AsyncMock()
    with pytest.raises(AdminError) as result:
        asyncio.run(adapter._commit(session))
    assert result.value.status == 412
    assert result.value.code == "precondition_failed"
    session.rollback.assert_awaited_once()


def test_version_mapping_is_required():
    class Bad(Base):
        __tablename__="concurrency_bad"
        id: Mapped[int]=mapped_column(primary_key=True)
        version: Mapped[int]=mapped_column(default=1)
    with pytest.raises(ValueError, match="version_id_col"):
        from pyntral.orm import MapperAdapter
        MapperAdapter(Resource(Bad,version_field="version"))
