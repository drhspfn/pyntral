from fastapi import FastAPI
from fastapi.testclient import TestClient
from pyntral import Admin, LocalAuth, hash_password
import pytest

def test_locale_selected_in_schema_without_client_token():
    app=FastAPI(); panel=Admin(app,session_factory=lambda:None,
        auth=LocalAuth('admin',hash_password('password-1234')),
        secret_key='x'*64, secure_cookie=False, default_locale='ru',
        translations={'ru':{'nav.overview':'Обзор'}})
    with TestClient(app) as c:
        assert c.post('/admin/auth/login',json={'username':'admin','password':'password-1234'}).status_code==200
        schema=c.get('/admin/api/schema').json()
        assert schema['localization']=={'code':'ru','messages':{'nav.overview':'Обзор'}}
        assert c.get('/admin/api/schema?locale=admin').json()['localization']['code']=='ru'

def test_invalid_locale_fails_early():
    with pytest.raises(ValueError, match='default_locale'):
        Admin(FastAPI(),session_factory=lambda:None,
              auth=LocalAuth('admin',hash_password('password-1234')),
              secret_key='x'*64, secure_cookie=False, default_locale='../../secrets')
