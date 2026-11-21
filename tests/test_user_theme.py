from fastapi import FastAPI
from fastapi.testclient import TestClient
from pyntral import Admin, CallbackAuth, Principal


def test_resolved_theme_is_user_specific_and_validated():
    async def login(username, password):
        return Principal(id=username, username=username, roles=[username])

    app=FastAPI()
    Admin(app,session_factory=lambda: None,auth=CallbackAuth(login),
          secret_key="q"*64,secure_cookie=False,
          theme={"light":{"primary":"#888888"}},
          theme_resolver=lambda principal: {
              "default": "dark" if principal.id=="alice" else "light",
              "tokens": {"light":{"primary":"#112233"}} if principal.id=="bob" else {"dark":{"primary":"#556677"}},
          })
    with TestClient(app) as client:
        for username, expected_mode, expected_color in (("alice","dark","#556677"), ("bob","light","#112233")):
            assert client.post("/admin/auth/login",json={"username":username,"password":"x"}).status_code==200
            theme=client.get("/admin/api/schema").json()["theme"]
            assert theme["default"]==expected_mode
            assert theme["tokens"][expected_mode]["primary"]==expected_color
