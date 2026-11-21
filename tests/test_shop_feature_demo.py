"""End-to-end checks for every newly demonstrated Shop capability."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from pyntral import hash_password


def test_shop_feature_showcase(tmp_path: Path, monkeypatch):
    db = tmp_path / "shop-feature-demo.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db.as_posix()}")
    monkeypatch.setenv("ADMIN_USERNAME", "shop-admin")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", hash_password("test-password"))
    monkeypatch.setenv("APP_SECRET_KEY", "shop-feature-demo-secret-key-please-do-not-use-in-production")
    monkeypatch.setenv("ADMIN_SECURE_COOKIE", "false")
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))

    sys.modules.pop("examples.shop.app", None)
    demo = importlib.import_module("examples.shop.app")
    try:
        with TestClient(demo.app) as client:
            login = client.post("/admin/auth/login",
                                json={"username": "shop-admin", "password": "test-password"})
            assert login.status_code == 200, login.text
            csrf = {"X-CSRF-Token": login.json()["csrf"]}

            schema = client.get("/admin/api/schema").json()
            resources = {resource["id"]: resource for resource in schema["resources"]}
            customers = resources["customers"]
            email = next(field for field in customers["fields"] if field["name"] == "email")
            assert email["views"]["list"]["visible"] is False
            assert email["views"]["edit"]["readonly"] is True
            assert email["views"]["show"]["visible"] is True
            actions = {action["name"]: action["kind"] for action in customers["actions"]}
            assert actions["archive_selected"] == "bulk"
            assert actions["reactivate_all"] == "resource"

            assert resources["tags"]["crudViews"] == {"list": "tags-list"}
            assert any(rel["name"] == "tags" and rel.get("editable")
                       for rel in resources["products"]["relationships"])
            assert client.get("/admin/api/resources/tags").json()["total"] >= 4
            listing = client.get("/admin/api/resources/customers")
            assert listing.status_code == 200
            assert "email" not in listing.json()["items"][0]
            assert "email" in client.get("/admin/api/resources/customers/1").json()["record"]
            assert client.patch("/admin/api/resources/customers/1", json={"email": "bad@example.org"},
                                headers=csrf).status_code == 403

            bulk = client.post("/admin/api/resources/customers/actions/archive_selected",
                               json={"ids": [1, 2]}, headers=csrf)
            assert bulk.status_code == 200, bulk.text
            assert bulk.json()["result"] == {"archived": 2}
            with demo.SessionLocal() as session:
                assert session.get(demo.Customer, 1).active is False
                assert session.get(demo.Customer, 2).active is False

            act = client.post("/admin/api/resources/customers/actions/reactivate_all",
                              json={}, headers=csrf)
            assert act.status_code == 200, act.text
            assert act.json()["result"]["reactivated"] >= 2
            with demo.SessionLocal() as session:
                assert session.get(demo.Customer, 1).active is True

            url = "/admin/api/resources/products/1/relationships/tags"
            current = client.get(url)
            assert current.status_code == 200, current.text
            linked = {item["id"] for item in current.json()["items"]}
            tags = client.get("/admin/api/resources/tags").json()["items"]
            available = next(tag["id"] for tag in tags if tag["id"] not in linked)

            response = client.post(url + "/attach", json={"id": available}, headers=csrf)
            assert response.status_code == 200, response.text
            assert available in {item["id"] for item in client.get(url).json()["items"]}
            response = client.post(url + "/detach", json={"id": available}, headers=csrf)
            assert response.status_code == 200, response.text
            assert available not in {item["id"] for item in client.get(url).json()["items"]}
            assert client.get(f"/admin/api/resources/tags/{available}").status_code == 200

            created = client.post(url + "/create",
                                  json={"name": "Demo test label", "color": "#123456"},
                                  headers=csrf)
            assert created.status_code == 201, created.text
            assert created.json()["record"]["name"] == "Demo test label"

        # Repeat seeding without dropping or overwriting existing customer data.
        demo.seed()
        with demo.SessionLocal() as session:
            from sqlalchemy import func, select
            assert session.scalar(select(func.count()).select_from(demo.Tag)) == 5
            assert session.scalar(select(func.count()).select_from(demo.Customer)) == 12
    finally:
        demo.engine.dispose()
        sys.modules.pop("examples.shop.app", None)
