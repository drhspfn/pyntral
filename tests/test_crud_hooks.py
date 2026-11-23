from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool
from pyntral import Admin, CallbackAuth, Principal, Resource, ResourceHook
from pyntral.orm import AdminError

class Base(DeclarativeBase):
    pass

class Inventory(Base):
    __tablename__ = "hook_inventory"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    stock: Mapped[int]


def test_hooks_reject_invalid_input_and_run_after_commit():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sf = sessionmaker(engine, expire_on_commit=False)
    seen=[]
    def before(ctx):
        if int(ctx.payload.get("stock", 0)) < 0:
            raise AdminError(422, "Invalid stock")
    def after(ctx):
        assert sf().scalar(select(Inventory).where(Inventory.id == ctx.record.id)) is not None
        seen.append(ctx.operation)
    async def login(_u,_p): return Principal(id="admin", username="admin", roles=["admin"])
    app = FastAPI()
    panel=Admin(app, session_factory=sf, auth=CallbackAuth(login), secret_key="x"*64, secure_cookie=False)
    panel.add_resource(Resource(Inventory, hooks=[ResourceHook(before_create=before, before_update=before, after_create=after)]))
    with TestClient(app) as client:
        token=client.post("/admin/auth/login",json={"username":"admin","password":"x"}).json()["csrf"]
        h={"X-CSRF-Token":token}
        assert client.post("/admin/api/resources/inventorys",json={"name":"Bad","stock":-2},headers=h).status_code==422
        ok=client.post("/admin/api/resources/inventorys",json={"name":"Good","stock":3},headers=h)
        assert ok.status_code==201,ok.text
        assert seen==["create"]
        id=ok.json()["record"]["id"]
        assert client.patch(f"/admin/api/resources/inventorys/{id}",json={"stock":-1},headers=h).status_code==422
        with sf() as s:
            assert s.get(Inventory,id).stock==3
    engine.dispose()
