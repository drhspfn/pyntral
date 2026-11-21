from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool
from pyntral import Admin, CallbackAuth, Principal, Resource, VirtualField

class Base(DeclarativeBase): pass
class Article(Base):
    __tablename__="vf_articles"
    id: Mapped[int]=mapped_column(primary_key=True)
    title: Mapped[str]=mapped_column(String(50))
    secret: Mapped[str]=mapped_column(String(200),default="")

def test_virtual_fields_are_guarded_and_not_returned_when_write_only():
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(engine); sf=sessionmaker(engine,expire_on_commit=False)
    async def login(u,p): return Principal(id="a",username="a",roles=["admin"])
    app=FastAPI()
    admin=Admin(app,session_factory=sf,auth=CallbackAuth(login),secret_key="s"*64,secure_cookie=False)
    admin.add_resource(Resource(Article,fields={"secret":__import__('pyntral').Field(visible=False)},
        list_fields=["id","title","summary"],virtual_fields={
           "summary":VirtualField(getter=lambda record: f"Article {record.id}: {record.title}"),
           "new_secret":VirtualField(setter=lambda record,value: setattr(record,"secret",str(value))),
        }))
    with TestClient(app) as c:
        csrf=c.post("/admin/auth/login",json={"username":"a","password":"x"}).json()["csrf"]
        h={"X-CSRF-Token":csrf}
        result=c.post("/admin/api/resources/articles",headers=h,json={"title":"X","new_secret":"not-serialized"})
        assert result.status_code==201,result.text
        assert 'new_secret' not in result.text and 'secret' not in result.text
        id=result.json()["record"]["id"]
        listed=c.get("/admin/api/resources/articles").json()
        assert listed["items"][0]["summary"]==f"Article {id}: X"
        assert "new_secret" not in listed["items"][0]
        edited=c.patch(f"/admin/api/resources/articles/{id}",headers=h,json={"new_secret":"changed"})
        assert edited.status_code==200,edited.text
        with sf() as session: assert session.get(Article,id).secret=="changed"
        assert c.patch(f"/admin/api/resources/articles/{id}",headers=h,json={"summary":"write"}).status_code in (403,422)
    engine.dispose()
