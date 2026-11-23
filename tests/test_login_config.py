"""Public login presentation is intentionally separate from authenticated metadata."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from pyntral import Admin, CallbackAuth, LoginConfig, Principal, SidebarConfig, SidebarHeader, SvgIcon


def test_public_login_config_never_resolves_private_preferences():
    calls = []
    logo = SvgIcon('<svg xmlns="http://www.w3.org/2000/svg"/>')

    async def login(username, password):
        return Principal(id=username, username=username, roles=["admin"])

    def resolve(principal):
        calls.append(principal.id)
        return {"default": "light", "tokens": {"light": {"primary": "#112233"}}}

    app = FastAPI()
    Admin(app, session_factory=lambda: None, auth=CallbackAuth(login),
          secret_key="a" * 64, secure_cookie=False, title="Workspace", path="/ops",
          sidebar=SidebarConfig(header=SidebarHeader(icon=logo, subtitle="Operations")),
          login=LoginConfig(layout="split", side_position="right", card=False,
                            form_align="left", max_width=400, footer="Public notice"),
          default_theme="dark", animations=False,
          theme={"dark": {"primary": "#556677", "login-card-radius": "12px"}},
          theme_resolver=resolve, default_locale="ru",
          translations={"ru": {"login.submit": "Войти", "private.note": "not public"}})
    with TestClient(app, root_path="/product") as client:
        url = "/product/ops/auth/config"
        response = client.get(url)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        public = response.json()
        assert set(public) == {"login", "theme", "localization"}
        config = public["login"]
        assert config["layout"] == "split" and config["sidePosition"] == "right"
        assert config["brandPosition"] == "side"
        assert config["brand"]["title"] == "Workspace"
        assert config["brand"]["subtitle"] == "Operations"
        assert config["brand"]["icon"]["kind"] == "svg"
        assert config["brand"]["align"] == "left" and config["brand"]["direction"] == "horizontal"
        assert config["maxWidth"] == 400 and not config["card"]
        assert config["footer"] == "Public notice"
        assert public["theme"] == {"default": "dark", "animations": False,
                                   "tokens": {"light": {}, "dark": {"primary": "#556677", "login-card-radius": "12px"}}}
        assert public["localization"] == {"code": "ru", "messages": {"login.submit": "Войти"}}
        assert calls == []
        assert client.get("/product/ops/api/schema").status_code == 401
        auth = client.post("/product/ops/auth/login", json={"username": "admin", "password": "x"})
        assert auth.status_code == 200, auth.text
        private = client.get("/product/ops/api/schema").json()
        assert private["theme"]["default"] == "light"
        assert private["theme"]["tokens"]["light"]["primary"] == "#112233"
        assert calls == ["admin"]
        assert client.get(url).json() == public
        assert calls == ["admin"]


def test_default_login_and_brand_overrides():
    default = LoginConfig().metadata("Example", None)
    assert default["layout"] == "centered" and default["card"]
    assert default["brandPosition"] == "form"
    assert default["brand"]["title"] == "Example"
    assert default["brand"]["direction"] == "vertical"
    assert default["brand"]["align"] == "center"
    assert default["showThemeToggle"] and default["showPasswordToggle"]
    assert LoginConfig(brand_position="hidden").metadata("App", None)["brand"] is None
    override = LoginConfig(brand=SidebarHeader(title="Login brand", icon=None),
                           brand_align="right", brand_direction="horizontal",
                           show_theme_toggle=False, show_password_toggle=False).metadata("App", SidebarHeader(title="Sidebar"))
    assert override["brand"]["title"] == "Login brand"
    assert override["brand"]["icon"] is None
    assert override["brand"]["align"] == "right"
    assert not override["showThemeToggle"] and not override["showPasswordToggle"]


@pytest.mark.parametrize("kwargs", [{"layout": "unknown"}, {"brand_position": "side"}, {"max_width": 200},
                                    {"max_width": 800}, {"title": ""}, {"form_align": "stretch"},
                                    {"brand_direction": "diagonal"}, {"show_theme_toggle": 1}])
def test_invalid_login_configuration(kwargs):
    with pytest.raises((ValueError, TypeError)):
        LoginConfig(**kwargs)
