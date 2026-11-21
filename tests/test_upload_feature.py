from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool
from pyntral import Admin, CallbackAuth, Principal, Resource, UploadFeature, UploadBase, UploadEntry, LocalStorage
import pytest

class Base(DeclarativeBase): pass
class Doc(Base):
    __tablename__ = "upload_docs"
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(50))

def test_secure_local_upload_download_delete(tmp_path):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine);UploadBase.metadata.create_all(engine)
    sf=sessionmaker(engine,expire_on_commit=False)
    async def login(u,p):return Principal(id='a',username='a',roles=['admin'])
    app=FastAPI();panel=Admin(app,session_factory=sf,auth=CallbackAuth(login),secret_key='s'*64,
                              secure_cookie=False,storage=LocalStorage(tmp_path/'objects'))
    panel.add_resource(Resource(Doc,features=[UploadFeature(max_bytes=10)]))
    with TestClient(app) as c:
        login=c.post('/admin/auth/login',json={'username':'a','password':'x'})
        h={'X-CSRF-Token':login.json()['csrf']}
        record=c.post('/admin/api/resources/docs',json={'name':'doc'},headers=h).json()['record']['id']
        url=f'/admin/api/resources/docs/{record}/uploads'
        assert c.post(url,content=b'abc').status_code==403
        assert c.post(url,content=b'12345678901',headers={**h,'X-Filename':'x.bin'}).status_code==413
        upload=c.post(url,content=b'pdf',headers={**h,'X-Filename':'../test.html','Content-Type':'text/html'})
        assert upload.status_code==201,upload.text
        id=upload.json()['id']
        assert upload.json()['filename']=='test.html'
        items=c.get(url).json()['items'];assert len(items)==1
        download=c.get(f'/admin/api/uploads/{id}')
        assert download.status_code==200 and download.content==b'pdf'
        assert 'attachment' in download.headers['content-disposition']
        c.post('/admin/auth/logout',headers=h)
        assert c.get(f'/admin/api/uploads/{id}').status_code==401
        login=c.post('/admin/auth/login',json={'username':'a','password':'x'})
        csrf={'X-CSRF-Token':login.json()['csrf']}
        assert c.delete(f'/admin/api/uploads/{id}',headers=csrf).status_code==200
        assert c.get(url).json()['items']==[]
    engine.dispose()

def test_upload_requires_storage_and_rejects_path_traversal(tmp_path):
    storage=LocalStorage(tmp_path/'private')
    with pytest.raises(ValueError):storage._path('../escape')
    app=FastAPI()
    from pyntral import LocalAuth, hash_password
    a=Admin(app,session_factory=lambda:None,auth=LocalAuth('admin',hash_password('longpassword')),
            secret_key='x'*64,secure_cookie=False)
    with pytest.raises(ValueError,match='storage'):
        a.add_resource(Resource(Doc,features=[UploadFeature()]))
