"""The installed Python package serves its embedded SPA without a frontend toolchain."""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from pyntral import Admin, LocalAuth, hash_password


def test_generic_spa_is_served_from_package_data(tmp_path, monkeypatch):
    import pyntral.admin as admin_module

    package = tmp_path / "installed" / "pyntral"
    assets = package / "web_dist" / "assets"
    assets.mkdir(parents=True)
    (package / "web_dist" / "index.html").write_text("<html>Pyntral packaged</html>")
    (assets / "main.js").write_text("console.log('packaged')")
    # Pretend the code was imported from the installed wheel and the host has
    # not compiled a custom .pyntral/dist/ bundle.
    monkeypatch.setattr(admin_module, "__file__", str(package / "admin.py"))
    empty_host = tmp_path / "empty"
    empty_host.mkdir()
    monkeypatch.chdir(empty_host)
    monkeypatch.delenv("PYNTRAL_DIST", raising=False)

    app = FastAPI()
    admin = Admin(
        app, session_factory=lambda: None,
        auth=LocalAuth("demo", hash_password("long-password")),
        secret_key="a" * 48, secure_cookie=False,
    )
    assert admin._dist() == package / "web_dist"
    with TestClient(app) as client:
        assert client.get("/admin/").text == "<html>Pyntral packaged</html>"
        assert client.get("/admin/resources/users/42").status_code == 200
        assert "packaged" in client.get("/admin/assets/main.js").text
        assert client.get("/admin/assets/missing.js").status_code == 404
        assert client.get("/admin/api/schema").status_code == 401


def test_custom_bundle_takes_precedence(tmp_path, monkeypatch):
    app = FastAPI()
    auth = LocalAuth("demo", hash_password("long-password"))
    local = tmp_path / ".pyntral" / "dist"
    local.mkdir(parents=True)
    (local / "index.html").write_text("custom")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PYNTRAL_DIST", raising=False)
    admin = Admin(app, session_factory=lambda: None, auth=auth,
                  secret_key="b" * 48, secure_cookie=False)
    assert admin._dist() == local.resolve()
    with TestClient(app) as client:
        assert client.get("/admin/").text == "custom"

    direct = tmp_path / "another-dist"
    direct.mkdir()
    (direct / "index.html").write_text("explicit")
    admin_with_override = Admin(FastAPI(), session_factory=lambda: None, auth=auth,
                                secret_key="c" * 48, secure_cookie=False,
                                dist_dir=direct)
    assert admin_with_override._dist() == direct


def test_installed_wheel_smoke_ignores_checkout_bundle(tmp_path, monkeypatch):
    """A custom checkout build must not shadow embedded wheel assets in CI."""
    import pyntral
    import pyntral.admin as admin_module
    from runpy import run_path
    smoke_installed = run_path(str(Path(__file__).resolve().parents[1] / "scripts" / "smoke_installed.py"))["main"]

    package = tmp_path / "installed" / "pyntral"
    assets = package / "web_dist" / "assets"
    assets.mkdir(parents=True)
    (package / "web_dist" / "index.html").write_text(
        '<html><head><base data-pyntral-base href="./"><title>Pyntral</title>'
        '<link rel="icon" href="./auth/favicon" /></head><body>generic wheel</body></html>', encoding="utf-8",
    )
    (package / "web_dist" / "favicon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
    (assets / "generic.js").write_text("console.log('wheel')")
    monkeypatch.setattr(pyntral, "__file__", str(package / "__init__.py"))
    monkeypatch.setattr(admin_module, "__file__", str(package / "admin.py"))

    checkout = tmp_path / "checkout"
    custom = checkout / ".pyntral" / "dist"
    custom.mkdir(parents=True)
    (custom / "index.html").write_text("<html>custom checkout</html>")
    (custom / "assets").mkdir()
    (custom / "assets" / "custom.js").write_text("console.log('custom')")
    monkeypatch.chdir(checkout)
    monkeypatch.setenv("PYNTRAL_DIST", str(custom))

    smoke_installed()
    assert Path.cwd() == checkout
    assert os.environ["PYNTRAL_DIST"] == str(custom)


def test_bundle_mount_respects_reverse_proxy_prefix(tmp_path):
    from urllib.parse import urljoin
    from re import search

    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "main.js").write_text("window.integrationReady = true;", encoding="utf-8")
    (tmp_path / "index.html").write_text(
        '<base data-pyntral-base href="./" /><script type="module" src="./assets/main.js"></script>',
        encoding="utf-8",
    )
    app = FastAPI()
    Admin(app, session_factory=lambda: None, path="/ops", dist_dir=tmp_path,
          auth=LocalAuth("demo", hash_password("example")), secret_key="x" * 48)
    with TestClient(app, root_path="/prefix") as client:
        page = client.get("/prefix/ops/resources/example/42")
        assert page.status_code == 200
        base = search(r'<base [^>]*href="([^"]+)"', page.text).group(1)
        script = search(r'<script [^>]*src="([^"]+)"', page.text).group(1)
        assert base == "/prefix/ops/"
        assert client.get(urljoin(base, script)).status_code == 200
        assert client.get("/prefix/ops/auth/me").headers["cache-control"] == "no-store"

def test_browser_branding_escapes_title_and_inherits_svg(tmp_path):
    from pyntral import SidebarConfig, SidebarHeader, SvgIcon
    logo = SvgIcon('<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>')
    (tmp_path / "index.html").write_text(
        '<html><head><base data-pyntral-base href="./"/><title>Pyntral</title>'
        '<link rel="icon" href="./favicon.svg" type="image/svg+xml"/></head></html>', encoding="utf-8")
    app = FastAPI()
    Admin(app, session_factory=lambda: None, auth=LocalAuth("demo", hash_password("example")),
          secret_key="x" * 48, path="/ops", dist_dir=tmp_path, title="Atlas <Admin> & tools",
          sidebar=SidebarConfig(header=SidebarHeader(icon=logo)))
    with TestClient(app, root_path="/prefix") as client:
        html = client.get("/prefix/ops/").text
        assert "<title>Atlas &lt;Admin&gt; &amp; tools</title>" in html
        assert 'href="/prefix/ops/auth/favicon"' in html
        for route in ("auth/favicon", "favicon.svg"):
            icon = client.get("/prefix/ops/" + route)
            assert icon.content == logo.svg.encode()
            assert icon.headers["content-type"].startswith("image/svg+xml")
            assert "sandbox" in icon.headers["content-security-policy"]
        assert client.get("/prefix/ops/auth/config").json()["title"] == "Atlas <Admin> & tools"


def test_explicit_favicon_and_default_source_without_bundle(tmp_path):
    from pyntral import SvgIcon, SidebarConfig, SidebarHeader
    import pytest
    common = dict(session_factory=lambda: None, auth=LocalAuth("demo", hash_password("example")),
                  secret_key="x" * 48, dist_dir=tmp_path)
    file = tmp_path / "icon.svg"
    file.write_text('<svg xmlns="http://www.w3.org/2000/svg"><circle r="1"/></svg>')
    app = FastAPI()
    Admin(app, **common, favicon=file, sidebar=SidebarConfig(header=SidebarHeader(
        icon=SvgIcon('<svg xmlns="http://www.w3.org/2000/svg"/>'))))
    with TestClient(app) as client:
        assert client.get("/admin/auth/favicon").content == file.read_bytes()
    default = FastAPI()
    Admin(default, **common)
    with TestClient(default) as client:
        assert client.get("/admin/auth/favicon").status_code == 200
    file.write_text("<html/>")
    with pytest.raises(ValueError):
        Admin(FastAPI(), **common, favicon=file)
