"""Declarative sidebar and icon contracts."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool
import pytest

from pyntral import (Admin, CallbackAuth, Principal, Resource, Page, NavigationGroup,
                     Action, SidebarConfig, SidebarHeader, SidebarFooter, SvgIcon, ImageIcon)
from pyntral.sidebar import icon_metadata


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "sidebar_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))


def test_sidebar_config_and_icon_metadata_in_schema(tmp_path):
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M0 0L24 24"/></svg>'
    path = tmp_path / "logo.svg"
    path.write_text(svg, encoding="utf-8")
    logo = SvgIcon.from_file(path)
    theme_icon = ImageIcon(light="/static/dark.svg", dark="/static/light.svg")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    app = FastAPI()

    async def login(username, password):
        return Principal(id=username, username=username, roles=["admin"])

    admin = Admin(app, session_factory=sessionmaker(engine), auth=CallbackAuth(login),
                  secret_key="s" * 64, secure_cookie=False, title="My shop",
                  sidebar=SidebarConfig(
                      width=280, min_width=200, max_width=440, mobile_width=260,
                      show_icons=False, resizable=False, icon_size=18,
                      indent=6, max_indent_depth=4, dashboard_icon=None,
                      header=SidebarHeader(icon=logo, subtitle="Workspace", align="center",
                                           direction="vertical", logo_width=120, icon_background=False),
                      footer=SidebarFooter(show_avatar=False, show_roles=False),
                      header_component="shop-header", footer_component="shop-footer",
                      item_component="shop-item"))
    admin.add_group(NavigationGroup("Shop", icon=None))
    admin.add_resource(Resource(Item, name="items", navigation="Shop", icon=theme_icon,
                                actions=[Action("inspect", lambda *_: None, icon=logo)]))
    admin.add_page(Page("insights", "Insights", "insights", icon="chart-column", navigation="Shop"))
    with TestClient(app) as client:
        assert client.post("/admin/auth/login", json={"username": "admin", "password": "x"}).status_code == 200
        response = client.get("/admin/api/schema")
        assert response.status_code == 200, response.text
        schema = response.json()
        sidebar = schema["navigation"]["sidebar"]
        assert sidebar["width"] == 280 and sidebar["minWidth"] == 200
        assert sidebar["maxWidth"] == 440 and sidebar["mobileWidth"] == 260
        assert not sidebar["showIcons"] and not sidebar["resizable"]
        assert sidebar["dashboardIcon"] is None
        assert sidebar["iconSize"] == 18 and sidebar["indent"] == 6 and sidebar["maxIndentDepth"] == 4
        assert sidebar["header"]["title"] == "My shop"
        assert sidebar["header"]["icon"] == {"kind": "svg", "svg": svg}
        assert sidebar["header"]["direction"] == "vertical" and sidebar["header"]["align"] == "center"
        assert sidebar["footer"]["showAvatar"] is False and sidebar["footer"]["showRoles"] is False
        assert (sidebar["headerComponent"], sidebar["footerComponent"], sidebar["itemComponent"]) == (
            "shop-header", "shop-footer", "shop-item")
        assert schema["navigation"]["groups"][0]["icon"] is None
        assert schema["resources"][0]["icon"] == icon_metadata(theme_icon)
        assert schema["resources"][0]["actions"][0]["icon"] == icon_metadata(logo)
        assert schema["pages"][0]["icon"] == "chart-column"
    engine.dispose()


def test_default_and_hidden_regions():
    default = SidebarConfig().metadata("App")
    assert default["header"]["title"] == "App"
    assert default["header"]["icon"] == "command"
    assert default["width"] == 238 and default["resizable"]
    hidden = SidebarConfig(header=None, footer=None).metadata("App")
    assert hidden["header"] is None and hidden["footer"] is None
    assert icon_metadata("shopping-cart") == "shopping-cart"
    assert icon_metadata(None) is None


@pytest.mark.parametrize("value", ["javascript:alert(1)", "data:text/html,x", "//host/x",
                                  "https://user:pass@host/x", "/bad path", ""])
def test_reject_unsafe_image_urls(value):
    with pytest.raises(ValueError):
        ImageIcon(src=value)


@pytest.mark.parametrize("value", ["<html/>", "<svg", '<!DOCTYPE svg [<!ENTITY x "x">]><svg>&x;</svg>'])
def test_reject_invalid_svg(value):
    with pytest.raises(ValueError):
        SvgIcon(value)


def test_invalid_sidebar_dimensions():
    for kwargs in ({"min_width": 300}, {"max_width": 700}, {"indent": -1}, {"mobile_width": 100}):
        with pytest.raises(ValueError):
            SidebarConfig(**kwargs)
    with pytest.raises(ValueError):
        SidebarHeader(align="invalid")
