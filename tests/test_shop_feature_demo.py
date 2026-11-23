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
            public = client.get("/admin/auth/config").json()
            assert public["login"]["layout"] in ("centered", "split")
            assert public["login"]["brand"]["title"] == "Shop demo"
            assert public["login"]["brand"]["icon"]["kind"] == "svg"
            assert public["theme"]["tokens"]["light"]["primary"] == "#276b9e"
            login = client.post("/admin/auth/login", json={"username": "shop-admin", "password": "test-password"})
            assert login.status_code == 200, login.text
            csrf = {"X-CSRF-Token": login.json()["csrf"]}

            schema = client.get("/admin/api/schema").json()
            resources = {resource["id"]: resource for resource in schema["resources"]}
            sidebar = schema["navigation"]["sidebar"]
            assert sidebar["width"] == 260 and sidebar["resizable"]
            assert sidebar["header"]["title"] == "Shop demo"
            assert sidebar["header"]["subtitle"] == "Commerce workspace"
            assert sidebar["header"]["icon"]["kind"] == "svg"
            assert (sidebar["headerComponent"], sidebar["footerComponent"], sidebar["itemComponent"]) == (
                "shop-header", "shop-footer", "shop-item")
            assert resources["file-assets"]["icon"]["kind"] == "image"
            assert resources["editorial-drafts"]["uploadMaxBytes"] == 2_000_000
            products = resources["products"]
            assert any(job["name"] == "inventory-report" for job in products["jobs"])
            job_url = "/admin/api/resources/products/jobs/inventory-report"
            assert client.post(job_url, json={}).status_code == 403
            started = client.post(job_url, json={}, headers=csrf)
            assert started.status_code == 202, started.text
            job_id = started.json()["job"]["id"]
            polled = client.get(f"/admin/api/jobs/{job_id}")
            assert polled.status_code == 200, polled.text
            assert polled.json()["job"]["status"] in ("queued", "running", "completed")
            assert "result" not in polled.json()["job"]
            cancel = client.delete(f"/admin/api/jobs/{job_id}", headers=csrf)
            assert cancel.status_code == 200, cancel.text
            locations = resources["shipping-locations"]
            city_field = next(field for field in locations["fields"] if field["name"] == "city")
            assert city_field["dependency"] == {
                "source": "country", "bridge": "shipping-city-options",
            }
            options = client.post("/admin/api/bridge/shipping-city-options",
                                  json={"country": "Moldova"}, headers=csrf)
            assert options.status_code == 200, options.text
            assert {value["value"] for value in options.json()["result"]["options"]} == {
                "Bălți", "Chișinău", "Cahul",
            }
            assert client.post("/admin/api/resources/shipping-locations",
                               json={"country": "Moldova", "city": "Lviv"},
                               headers=csrf).status_code == 422
            added = client.post("/admin/api/resources/shipping-locations",
                                json={"country": "Moldova", "city": "Cahul"}, headers=csrf)
            assert added.status_code == 201, added.text
            customers = resources["customers"]
            email = next(field for field in customers["fields"] if field["name"] == "email")
            assert email["views"]["list"]["visible"] is False
            assert email["views"]["edit"]["readonly"] is True
            assert email["views"]["show"]["visible"] is True
            actions = {action["name"]: action["kind"] for action in customers["actions"]}
            assert actions["archive_selected"] == "bulk"
            assert actions["reactivate_all"] == "resource"

            tag_resource = resources["tags"]
            assert tag_resource["crudViews"] == {"list": "tags-list"}
            assert any(relation["name"] == "tags" and relation.get("editable")
                       for relation in resources["products"]["relationships"])
            tags = client.get("/admin/api/resources/tags").json()
            assert tags["total"] >= 4
            assert client.get("/admin/api/resources/customers").status_code == 200
            assert "email" not in client.get("/admin/api/resources/customers").json()["items"][0]
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

            resource_action = client.post("/admin/api/resources/customers/actions/reactivate_all",
                                          json={}, headers=csrf)
            assert resource_action.status_code == 200, resource_action.text
            assert resource_action.json()["result"]["reactivated"] >= 2
            with demo.SessionLocal() as session:
                assert session.get(demo.Customer, 1).active is True

            rel = "/admin/api/resources/products/1/relationships/tags"
            current = client.get(rel)
            assert current.status_code == 200, current.text
            currently_linked = {item["id"] for item in current.json()["items"]}
            all_tags = client.get("/admin/api/resources/tags").json()["items"]
            attach_id = next(tag["id"] for tag in all_tags if tag["id"] not in currently_linked)
            attached = client.post(rel + "/attach", json={"id": attach_id}, headers=csrf)
            assert attached.status_code == 200, attached.text
            assert attach_id in {item["id"] for item in client.get(rel).json()["items"]}
            detached = client.post(rel + "/detach", json={"id": attach_id}, headers=csrf)
            assert detached.status_code == 200, detached.text
            assert attach_id not in {item["id"] for item in client.get(rel).json()["items"]}
            assert client.get(f"/admin/api/resources/tags/{attach_id}").status_code == 200
            created = client.post(rel + "/create", json={"name": "Demo test label", "color": "#123456"},
                                  headers=csrf)
            assert created.status_code == 201, created.text
            assert created.json()["record"]["name"] == "Demo test label"

        # The demonstration is safe to start repeatedly with an existing database.
        demo.seed()
        with demo.SessionLocal() as session:
            from sqlalchemy import func, select
            assert session.scalar(select(func.count()).select_from(demo.Tag)) == 5
            assert session.scalar(select(func.count()).select_from(demo.Customer)) == 12
    finally:
        demo.engine.dispose()
        sys.modules.pop("examples.shop.app", None)
