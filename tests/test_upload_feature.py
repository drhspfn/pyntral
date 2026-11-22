import asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import String, create_engine, event, select
from sqlalchemy.exc import IntegrityError
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



@pytest.mark.parametrize("delete_owner", [False, True])
def test_attachment_deletion_commits_before_retrying_object_cleanup(tmp_path, monkeypatch, delete_owner):
    engine = create_engine(f"sqlite:///{(tmp_path / 'uploads.db').as_posix()}")
    Base.metadata.create_all(engine)
    UploadBase.metadata.create_all(engine)
    sessions = sessionmaker(engine)

    async def login(_user, _password):
        return Principal(id="owner", username="owner", roles=["admin"])

    storage = LocalStorage(tmp_path / "objects")
    app = FastAPI()
    panel = Admin(app, session_factory=sessions, auth=CallbackAuth(login), secret_key="s" * 64,
                  secure_cookie=False, storage=storage)
    panel.add_resource(Resource(Doc, features=[UploadFeature()]))
    client = TestClient(app)
    try:
        auth = client.post("/admin/auth/login", json={"username": "owner", "password": "fixture"})
        headers = {"X-CSRF-Token": auth.json()["csrf"]}
        document = "/admin/api/resources/docs"
        created = client.post(document, json={"name": "Document"}, headers=headers)
        record_id = created.json()["record"]["id"]
        owner_url = f"{document}/{record_id}"
        listed = f"{owner_url}/uploads"
        uploaded = client.post(f"{document}/0{record_id}/uploads", content=b"attachment", headers=headers)
        assert uploaded.status_code == 201, uploaded.text
        upload_id = uploaded.json()["id"]
        attachment = f"/admin/api/uploads/{upload_id}"
        assert client.get(listed).json()["items"][0]["id"] == upload_id
        with sessions() as session:
            entry = session.get(UploadEntry, upload_id)
            assert entry.record_id == str(record_id)
            object_key = entry.object_key

        def reject_commit(_session):
            raise IntegrityError(None, None, Exception("simulated transaction failure"))

        url = owner_url if delete_owner else attachment
        event.listen(sessions, "before_commit", reject_commit)
        try:
            assert client.delete(url, headers=headers).status_code == 409
        finally:
            event.remove(sessions, "before_commit", reject_commit)
        assert client.get(attachment).content == b"attachment"

        assert client.delete(url, headers=headers).status_code == 200
        assert client.get(attachment).status_code == 404
        if not delete_owner:
            assert client.get(listed).json()["items"] == []
        with sessions() as session:
            assert session.scalar(select(UploadEntry.record_id)) == ""

        async def unavailable(_storage, _key):
            raise OSError("storage unavailable")

        with monkeypatch.context() as patch:
            patch.setattr(LocalStorage, "delete", unavailable)
            asyncio.run(panel._cleanup_uploads())
            with sessions() as session:
                assert session.get(UploadEntry, upload_id) is not None
            assert (storage.root / object_key).is_file()

        asyncio.run(panel._cleanup_uploads())
        with sessions() as session:
            assert session.get(UploadEntry, upload_id) is None
        assert not (storage.root / object_key).exists()
    finally:
        client.close()
        engine.dispose()
