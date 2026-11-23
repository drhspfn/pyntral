from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import DateTime, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime
from pyntral import Admin, CallbackAuth, Principal, PasswordFeature, Resource, SoftDeleteFeature, verify_password

class Base(DeclarativeBase): pass
class User(Base):
    __tablename__="feature_account"
    id: Mapped[int]=mapped_column(primary_key=True)
    username: Mapped[str]=mapped_column(String(80))
    password_hash: Mapped[str]=mapped_column(String(255))
    deleted_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

def test_features_compose_securely_and_actions_remain_available():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine); sf=sessionmaker(engine,expire_on_commit=False)
    async def login(u,p):return Principal(id='u',username='u',roles=['admin'])
    app=FastAPI(); panel=Admin(app,session_factory=sf,auth=CallbackAuth(login),secret_key='y'*64,secure_cookie=False)
    panel.add_resource(Resource(User,name='accounts',features=[PasswordFeature(),SoftDeleteFeature()]))
    with TestClient(app) as client:
        token=client.post('/admin/auth/login',json={'username':'u','password':'p'}).json()['csrf']
        h={'X-CSRF-Token':token}
        resource = client.get("/admin/api/schema").json()["resources"][0]
        password = next(field for field in resource["fields"] if field["name"] == "new_password")
        assert password["widget"] == "password"
        assert password["views"]["create"]["visible"] and not password["views"]["show"]["visible"]
        bad=client.post('/admin/api/resources/accounts',json={'username':'a','new_password':'123'},headers=h)
        assert bad.status_code==422
        good=client.post('/admin/api/resources/accounts',json={'username':'a','new_password':'long-password-123'},headers=h)
        assert good.status_code==201,good.text
        assert 'password' not in good.text
        id=good.json()['record']['id']
        with sf() as s: assert verify_password('long-password-123',s.get(User,id).password_hash)
        assert client.delete(f'/admin/api/resources/accounts/{id}',headers=h).status_code==403
        archive=client.post(f'/admin/api/resources/accounts/{id}/actions/archive',headers=h,json={})
        assert archive.status_code==200,archive.text
        with sf() as s: assert s.get(User,id).deleted_at is not None
        restore=client.post(f'/admin/api/resources/accounts/{id}/actions/restore',headers=h,json={})
        assert restore.status_code==200,restore.text
        with sf() as s: assert s.get(User,id).deleted_at is None
    engine.dispose()
