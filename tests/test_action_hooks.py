"""Action hooks only run after authorization; before hooks can veto actions."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from pyntral import Action, Admin, CallbackAuth, Principal, Resource, ResourceHook
from pyntral.orm import AdminError


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "action_hooks"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40))


def test_action_hooks_check_permission_and_veto_without_running_handler():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions() as session:
        session.add(Item(name="example"))
        session.commit()
    seen=[]
    async def login(_u, _p): return Principal(id="one", username="one")
    async def authorize(_p, _r, action, _record): return action != "action:restricted"
    def before(ctx):
        seen.append(("before", ctx.action, ctx.record.id if ctx.record else None))
        if ctx.action == "reject": raise AdminError(422, "Action vetoed")
        ctx.payload["checked"] = True
    def after(ctx): seen.append(("after", ctx.action, ctx.record.id if ctx.record else None))
    def handle(record, session, principal, payload):
        seen.append(("handler", payload["checked"], record.id))
        return {"ok": True}

    app = FastAPI()
    panel = Admin(app, session_factory=sessions, auth=CallbackAuth(login, authorize=authorize),
                  secret_key="s"*64, secure_cookie=False)
    panel.add_resource(Resource(Item, hooks=[ResourceHook(before_action=before, after_action=after)],
        actions=[Action("go", handle), Action("reject", handle), Action("restricted", handle)]))
    with TestClient(app) as client:
        login_data = client.post("/admin/auth/login", json={"username":"one","password":"x"}).json()
        headers={"X-CSRF-Token":login_data["csrf"]}
        route="/admin/api/resources/items/1/actions/"
        assert client.post(route+"restricted",json={},headers=headers).status_code==403
        assert seen == []
        assert client.post(route+"reject",json={},headers=headers).status_code==422
        assert seen == [("before", "reject", 1)]
        good=client.post(route+"go",json={},headers=headers)
        assert good.status_code==200, good.text
        assert seen[-3:]==[("before", "go", 1), ("handler", True, 1), ("after", "go", 1)]
    engine.dispose()
