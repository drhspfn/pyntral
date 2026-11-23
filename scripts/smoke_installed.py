"""Smoke-test a pip-installed Pyntral wheel without Node.js or project UI sources."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pyntral import Admin, LocalAuth, SidebarConfig, SidebarHeader, SvgIcon, hash_password
import pyntral


def main() -> None:
    dist = Path(pyntral.__file__).resolve().parent / "web_dist"
    assert (dist / "index.html").is_file(), "Installed wheel is missing index.html"
    assets = sorted((dist / "assets").glob("*.js"))
    assert assets, "Installed wheel is missing compiled JavaScript"

    # The checkout may contain a separately built custom .pyntral/dist bundle.
    # Isolate the smoke test so Admin uses the wheel's default embedded SPA,
    # rather than resolving the checkout's bundle via the current directory.
    previous_cwd = Path.cwd()
    previous_dist = os.environ.pop("PYNTRAL_DIST", None)
    try:
        with TemporaryDirectory(prefix="pyntral-wheel-smoke-") as temp_dir:
            os.chdir(temp_dir)
            try:
                app = FastAPI()
                Admin(app, session_factory=lambda: None,
                      auth=LocalAuth("demo", hash_password("local-smoke-password")),
                      secret_key="smoke-test-only-secret-of-sufficient-length",
                      secure_cookie=False, title="Wheel workspace",
                      sidebar=SidebarConfig(header=SidebarHeader(icon=SvgIcon(
                          '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"/>'),
                          subtitle="No frontend build")))
                with TestClient(app) as client:
                    root = client.get("/admin/")
                    assert root.status_code == 200, root.text
                    assert "text/html" in root.headers["content-type"]
                    bundled = (dist / "index.html").read_text(encoding="utf-8")
                    assert root.text == bundled.replace(
                        '<base data-pyntral-base href="./"', '<base data-pyntral-base href="/admin/"', 1,
                    )
                    assert client.get("/admin/resources/anything").content == root.content
                    assert client.get("/admin/api/schema").status_code == 401
                    public = client.get("/admin/auth/config")
                    assert public.status_code == 200
                    assert public.json()["login"]["layout"] == "centered"
                    assert public.json()["login"]["brand"]["title"] == "Wheel workspace"
                    asset = client.get("/admin/assets/" + assets[0].name)
                    assert asset.status_code == 200, asset.text
                    assert asset.content == assets[0].read_bytes()
                    login = client.post("/admin/auth/login", json={"username": "demo", "password": "local-smoke-password"})
                    assert login.status_code == 200, login.text
                    schema = client.get("/admin/api/schema").json()
                    header = schema["navigation"]["sidebar"]["header"]
                    assert header["title"] == "Wheel workspace"
                    assert header["subtitle"] == "No frontend build"
                    assert header["icon"]["kind"] == "svg"
                proxy = FastAPI()
                Admin(proxy, path="/ops", session_factory=lambda: None,
                      auth=LocalAuth("demo", hash_password("local-smoke-password")),
                      secret_key="smoke-test-only-secret-of-sufficient-length",
                      secure_cookie=False)
                with TestClient(proxy, root_path="/product") as client:
                    nested = client.get("/product/ops/resources/anything")
                    assert nested.status_code == 200
                    assert '<base data-pyntral-base href="/product/ops/"' in nested.text
                    assert client.get(f"/product/ops/assets/{assets[0].name}").status_code == 200
                    assert client.get("/product/ops/api/schema").status_code == 401
            finally:
                os.chdir(previous_cwd)
    finally:
        if previous_dist is not None:
            os.environ["PYNTRAL_DIST"] = previous_dist
    print("Installed Python wheel serves generic SPA and protects the API")


if __name__ == "__main__":
    main()
