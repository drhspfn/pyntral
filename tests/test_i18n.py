from fastapi import FastAPI
from fastapi.testclient import TestClient
from pyntral import Admin, LocalAuth, hash_password
import pytest

def test_locale_selected_in_schema_without_client_token():
    app=FastAPI(); panel=Admin(app,session_factory=lambda:None,
        auth=LocalAuth('admin',hash_password('password-1234')),
        secret_key='x'*64, secure_cookie=False, default_locale='de',
        translations={'de':{'nav.overview':'Übersicht'}})
    with TestClient(app) as c:
        assert c.post('/admin/auth/login',json={'username':'admin','password':'password-1234'}).status_code==200
        schema=c.get('/admin/api/schema').json()
        assert schema['localization']=={'code':'de','messages':{'nav.overview':'Übersicht'}}
        assert c.get('/admin/api/schema?locale=admin').json()['localization']['code']=='de'

def test_invalid_locale_fails_early():
    with pytest.raises(ValueError, match='default_locale'):
        Admin(FastAPI(),session_factory=lambda:None,
              auth=LocalAuth('admin',hash_password('password-1234')),
              secret_key='x'*64, secure_cookie=False, default_locale='../../secrets')


def test_resource_labels_accept_literal_strings_and_locale_keys():
    from sqlalchemy import String
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
    from pyntral import Field, LayoutSection, Resource

    class Base(DeclarativeBase):
        pass

    class Article(Base):
        __tablename__ = "translated_articles"
        id: Mapped[int] = mapped_column(primary_key=True)
        title: Mapped[str] = mapped_column(String(80))

    app = FastAPI()
    panel = Admin(app, session_factory=lambda: None,
                  auth=LocalAuth("admin", hash_password("password-1234")),
                  secret_key="x" * 64, secure_cookie=False, default_locale="de",
                  translations={
                      "en": {"resources.articles": "Articles", "fields.title": "Title"},
                      "de": {"resources.articles": "Artikel", "fields.title": "Titel",
                             "sections.main": "Allgemein"},
                  })
    panel.add_resource(Resource(Article, label="@resources.articles",
                                fields={"title": Field(label="@fields.title"),
                                        "id": Field(label="Identifier")},
                                form_sections=[LayoutSection("main", "@sections.main", ["title"])]))
    with TestClient(app) as client:
        assert client.post("/admin/auth/login", json={
            "username": "admin", "password": "password-1234"}).status_code == 200
        schema = client.get("/admin/api/schema").json()
        resource = schema["resources"][0]
        assert resource["label"] == "Artikel"
        assert next(f for f in resource["fields"] if f["name"] == "title")["label"] == "Titel"
        assert next(f for f in resource["fields"] if f["name"] == "id")["label"] == "Identifier"
        assert resource["layouts"]["form"][0]["title"] == "Allgemein"
