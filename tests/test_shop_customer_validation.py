"""Shop Customer validation must execute on the server, not just in HTML."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from pyntral import hash_password


def test_customer_create_and_edit_validation(tmp_path: Path, monkeypatch):
    db = tmp_path / "customer-validation.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db.as_posix()}")
    monkeypatch.setenv("ADMIN_USERNAME", "shop-admin")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", hash_password("test-password"))
    monkeypatch.setenv("APP_SECRET_KEY", "shop-validation-test-secret-must-be-at-least-32-chars")
    monkeypatch.setenv("ADMIN_SECURE_COOKIE", "false")
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    sys.modules.pop("examples.shop.app", None)
    demo = importlib.import_module("examples.shop.app")
    try:
        with TestClient(demo.app) as client:
            login = client.post("/admin/auth/login", json={"username": "shop-admin", "password": "test-password"})
            assert login.status_code == 200, login.text
            csrf = {"X-CSRF-Token": login.json()["csrf"]}
            url = "/admin/api/resources/customers"
            initial = client.get(url).json()["total"]

            for email in ("123", "missing-at.example", "test@localhost", "name with space@example.org"):
                response = client.post(url, json={"name": "Test Person", "email": email}, headers=csrf)
                assert response.status_code == 422, response.text
                assert response.json()["error"]["details"] == {"fields": ["email"]}

            for name in ("", " ", "A"):
                response = client.post(url, json={"name": name, "email": "valid@example.org"}, headers=csrf)
                assert response.status_code == 422, response.text
                assert response.json()["error"]["details"] == {"fields": ["name"]}

            assert client.post(url, json={"name": "Test Person"}, headers=csrf).status_code == 422
            assert client.get(url).json()["total"] == initial
            created = client.post(url, json={"name": "  Test Person  ", "email": "new.customer@example.org"}, headers=csrf)
            assert created.status_code == 201, created.text
            record = created.json()["record"]
            assert record["name"] == "Test Person"
            assert record["email"] == "new.customer@example.org"

            duplicate = client.post(url, json={"name": "Another Person", "email": "new.customer@example.org"}, headers=csrf)
            assert duplicate.status_code == 409, duplicate.text
            for name in ("", "A", None):
                response = client.patch(f"{url}/{record['id']}", json={"name": name}, headers=csrf)
                assert response.status_code == 422, response.text
            updated = client.patch(f"{url}/{record['id']}", json={"name": "  Renamed Person  "}, headers=csrf)
            assert updated.status_code == 200, updated.text
            assert updated.json()["record"]["name"] == "Renamed Person"
    finally:
        demo.engine.dispose()
        sys.modules.pop("examples.shop.app", None)
