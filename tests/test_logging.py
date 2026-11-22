"""Logging behavior: scoped events, CLI defaults, privacy and optional adapters."""
from __future__ import annotations

import io
import json
import logging
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from pyntral import (
    Admin, LocalAuth, LoggingConfig, Resource,
    configure_logging, forward_to_loguru, hash_password, stop_logging,
)
from pyntral.logging import emit
from pyntral import cli


class Base(DeclarativeBase):
    pass


class Entry(Base):
    __tablename__ = "entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)


@pytest.fixture
def app_and_client():
    engine = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    app = FastAPI()
    admin = Admin(app, session_factory=sessionmaker(engine, expire_on_commit=False),
                  auth=LocalAuth("admin", hash_password("password123")),
                  secret_key="test" * 16, secure_cookie=False,
                  logging_config=LoggingConfig(http="all"))
    admin.add_resource(Resource(Entry))
    with TestClient(app) as client:
        yield admin, client
    engine.dispose()


def test_structured_events_do_not_log_credentials_or_queries(app_and_client):
    admin, client = app_and_client
    stream = io.StringIO()
    configure_logging(format="json", stream=stream)
    try:
        assert client.post("/admin/auth/login", json={"username": "root@private", "password": "super-secret"}).status_code == 401
        success = client.post("/admin/auth/login", json={"username": "admin", "password": "password123"})
        token = success.json()["csrf"]
        created = client.post("/admin/api/resources/entrys", json={"name": "private-secret-string"},
                              headers={"X-CSRF-Token": token})
        assert created.status_code == 201, created.text
        found = client.get("/admin/api/resources/entrys?filter.name.contains=private-secret-string")
        assert found.status_code == 200
        lines = [json.loads(line) for line in stream.getvalue().splitlines()]
        events = {line["event"] for line in lines}
        assert {"auth.login_failed", "auth.login_success", "resource.created", "http.request"} <= events
        assert not any(secret in stream.getvalue() for secret in
                       ("password123", "root@private", "super-secret", "private-secret-string"))
        assert all("request_id" in event for event in lines)
        assert "X-Request-ID" in created.headers
        assert "record_id" not in next(x for x in lines if x["event"] == "resource.created")
    finally:
        stop_logging()


def test_channel_and_event_filters():
    stream = io.StringIO()
    configure_logging(level="WARNING", stream=stream)
    try:
        cfg = LoggingConfig(level="WARNING", channels={"bridge": "DEBUG", "auth": "OFF"},
                            events={"bridge.noisy": False})
        emit(cfg, "bridge", "bridge.allowed", level="DEBUG", bridge="asset")
        emit(cfg, "bridge", "bridge.noisy", level="ERROR")
        emit(cfg, "auth", "auth.login_success", level="INFO")
        emit(cfg, "security", "security.denied", level="WARNING")
        output = stream.getvalue()
        assert "bridge.allowed" in output
        assert "bridge.noisy" not in output
        assert "login_success" not in output
        assert "security.denied" in output
    finally:
        stop_logging()


def test_file_channels_rotation_and_custom_formatter(tmp_path: Path):
    global_file = tmp_path / "logs" / "admin.jsonl"
    auth_file = tmp_path / "logs" / "auth.jsonl"
    configure_logging(level="INFO", console=False, format="json", file=global_file,
                      channel_files={"auth": auth_file}, max_bytes=1_000_000)
    try:
        emit(LoggingConfig(), "auth", "auth.login_success")
        emit(LoggingConfig(), "resource", "resource.created", resource="products")
    finally:
        stop_logging()
    global_events = [json.loads(line)["event"] for line in global_file.read_text().splitlines()]
    auth_events = [json.loads(line)["event"] for line in auth_file.read_text().splitlines()]
    assert global_events == ["auth.login_success", "resource.created"]
    assert auth_events == ["auth.login_success"]


def test_loguru_bridge_is_opt_in():
    loguru = pytest.importorskip("loguru")
    stream = io.StringIO()
    sink = loguru.logger.add(stream, format="{extra[channel]} | {extra[event]} | {message}")
    h = forward_to_loguru(loguru.logger)
    try:
        emit(LoggingConfig(), "action", "action.invoked", action="archive")
        assert "pyntral.action | action.invoked" in stream.getvalue()
    finally:
        logging.getLogger("pyntral").removeHandler(h)
        loguru.logger.remove(sink)


def test_cli_quiet_default_and_selective_http(tmp_path, monkeypatch):
    cli.sync_ui(tmp_path)
    monkeypatch.setattr(cli, "install_frontend", lambda *_: None)
    monkeypatch.setattr(cli, "generate_types", lambda *_: None)
    class FakeProcess:
        returncode = 0
        def poll(self):
            return self.returncode
        def wait(self, timeout=None):
            return self.returncode
    commands = []
    def fake_popen(cmd, **kwargs):
        commands.append((cmd, kwargs.get("env")))
        return FakeProcess()
    monkeypatch.setattr(cli.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(cli, "_npm_executable", lambda: "npm")
    assert cli.dev(tmp_path, "examples.shop.app:app", backend_port=8000,
                   frontend_port=5173, base="/admin/") == 0
    assert "--no-access-log" in commands[0][0]
    assert commands[0][1]["PYNTRAL_CLI_LOGGING"] == "1"
    commands.clear()
    assert cli.dev(tmp_path, "examples.shop.app:app", backend_port=8000,
                   frontend_port=5173, base="/admin/", access_log=True,
                   log_http="slow", log_channels=("bridge=OFF",), log_format="json") == 0
    assert "--no-access-log" not in commands[0][0]
    assert commands[0][1]["PYNTRAL_LOG_HTTP"] == "slow"
    assert commands[0][1]["PYNTRAL_LOG_CHANNELS"] == "bridge=OFF"
    with pytest.raises(ValueError, match="Unknown logging channel"):
        cli.dev(tmp_path, "examples.shop.app:app", backend_port=8000,
                frontend_port=5173, base="/admin/", log_channels=("oops=OFF",))


def test_invalid_configuration():
    with pytest.raises(ValueError):
        LoggingConfig(level="LOUD")
    with pytest.raises(ValueError):
        LoggingConfig(http="unlimited")
    with pytest.raises(ValueError):
        LoggingConfig(channels={"unknown": "INFO"})
    with pytest.raises(ValueError):
        LoggingConfig(events={"delete": "no"})
    with pytest.raises(ValueError):
        configure_logging(format="xml")


def test_http_error_only_and_record_ids_opt_in(app_and_client):
    admin, client = app_and_client
    admin.logging_config.http = "errors"
    admin.logging_config.include_record_id = True
    stream = io.StringIO()
    configure_logging(format="json", stream=stream)
    try:
        token = client.post("/admin/auth/login", json={"username": "admin", "password": "password123"}).json()["csrf"]
        response = client.get("/admin/api/resources/entrys?offset=0")
        assert response.status_code == 200
        first = client.post("/admin/api/resources/entrys", json={"name": "Alice"}, headers={"X-CSRF-Token": token})
        assert first.status_code == 201
        second = client.post("/admin/api/resources/entrys", json={"name": "Alice"}, headers={"X-CSRF-Token": token})
        assert second.status_code == 409
        events = [json.loads(line) for line in stream.getvalue().splitlines()]
        http = [record for record in events if record["event"] == "http.request"]
        assert len(http) == 1 and http[0]["status"] == 409
        assert "filter." not in stream.getvalue()
        created = next(record for record in events if record["event"] == "resource.created")
        assert created["record_id"] == first.json()["record"]["id"]
    finally:
        stop_logging()


def test_environment_channel_event_policy(monkeypatch):
    monkeypatch.setenv("PYNTRAL_LOG_CHANNELS", "bridge=OFF,resource=DEBUG")
    monkeypatch.setenv("PYNTRAL_LOG_EVENTS", "resource.deleted=OFF")
    cfg = LoggingConfig.from_environment()
    assert not cfg.enabled("resource", "resource.deleted", "ERROR")
    assert cfg.enabled("resource", "resource.created", "DEBUG")
    assert not cfg.enabled("bridge", "bridge.invoked", "ERROR")


def test_cli_event_filters_and_channel_file(tmp_path, monkeypatch):
    cli.sync_ui(tmp_path)
    monkeypatch.setattr(cli, "install_frontend", lambda *_: None)
    monkeypatch.setattr(cli, "generate_types", lambda *_: None)
    monkeypatch.setattr(cli, "_npm_executable", lambda: "npm")
    class Process:
        returncode = 0
        def poll(self):
            return self.returncode
        def wait(self, timeout=None):
            return self.returncode
    captures = []
    def fake_popen(command, **kwargs):
        captures.append(kwargs["env"])
        return Process()
    monkeypatch.setattr(cli.subprocess, "Popen", fake_popen)
    assert cli.dev(tmp_path, "examples.shop.app:app", backend_port=8000,
                   frontend_port=5173, base="/admin/", log_events=("bridge.invoked=OFF",),
                   channel_files=("auth=.pyntral/logs/auth.jsonl",)) == 0
    assert captures[0]["PYNTRAL_LOG_EVENTS"] == "bridge.invoked=OFF"
    paths = json.loads(captures[0]["PYNTRAL_LOG_CHANNEL_FILES"])
    assert Path(paths["auth"]) == tmp_path / ".pyntral" / "logs" / "auth.jsonl"
