"""Smoke-test a pip-installed Pyntral wheel without Node.js or project UI sources."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pyntral import Admin, LocalAuth, hash_password
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
                      secure_cookie=False)
                with TestClient(app) as client:
                    root = client.get("/admin/")
                    assert root.status_code == 200, root.text
                    assert "text/html" in root.headers["content-type"]
                    assert root.content == (dist / "index.html").read_bytes()
                    assert client.get("/admin/resources/anything").content == root.content
                    assert client.get("/admin/api/schema").status_code == 401
                    asset = client.get("/admin/assets/" + assets[0].name)
                    assert asset.status_code == 200, asset.text
                    assert asset.content == assets[0].read_bytes()
            finally:
                os.chdir(previous_cwd)
    finally:
        if previous_dist is not None:
            os.environ["PYNTRAL_DIST"] = previous_dist
    print("Installed Python wheel serves generic SPA and protects the API")


if __name__ == "__main__":
    main()
