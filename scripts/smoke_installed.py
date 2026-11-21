"""Smoke-test a pip-installed Pyntral wheel without Node.js or project UI sources."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pyntral import Admin, LocalAuth, hash_password
import pyntral


def main() -> None:
    dist = Path(pyntral.__file__).resolve().parent / "web_dist"
    assert (dist / "index.html").is_file(), "Installed wheel is missing index.html"
    assets = sorted((dist / "assets").glob("*.js"))
    assert assets, "Installed wheel is missing compiled JavaScript"

    app = FastAPI()
    Admin(app, session_factory=lambda: None,
          auth=LocalAuth("demo", hash_password("local-smoke-password")),
          secret_key="smoke-test-only-secret-of-sufficient-length",
          secure_cookie=False)
    with TestClient(app) as client:
        assert client.get("/admin/").status_code == 200
        assert "text/html" in client.get("/admin/").headers["content-type"]
        assert client.get("/admin/resources/anything").status_code == 200
        assert client.get("/admin/api/schema").status_code == 401
        response = client.get("/admin/assets/" + assets[0].name)
        assert response.status_code == 200, response.text
    print("Installed Python wheel serves generic SPA and protects the API")


if __name__ == "__main__":
    main()
