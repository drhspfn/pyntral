import json
from pathlib import Path

import pytest

from pyntral import cli


def test_sync_and_build_cache(tmp_path, monkeypatch):
    ui = cli.sync_ui(tmp_path)
    assert (ui / "package.json").is_file()
    assert cli.sync_ui(tmp_path) == ui
    assert (tmp_path / ".pyntral" / "ui" / ".source.sha256").is_file()
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        dist = tmp_path / ".pyntral" / "dist"
        dist.mkdir(parents=True, exist_ok=True)
        (dist / "index.html").write_text("<html></html>")

    monkeypatch.setattr(cli, "install_frontend", lambda project, ui: None)
    monkeypatch.setattr(cli.subprocess, "run", run)
    assert cli.build(tmp_path) == tmp_path / ".pyntral" / "dist"
    assert len(calls) == 1
    assert cli.build(tmp_path) == tmp_path / ".pyntral" / "dist"
    assert len(calls) == 1
    assert cli.build(tmp_path, force=True) == tmp_path / ".pyntral" / "dist"
    assert len(calls) == 2


def test_component_registration_and_rebuild(tmp_path, monkeypatch):
    cli.init_ui(tmp_path)
    assert (tmp_path / "pyntral.components.json").exists()
    assert len(cli._component_fingerprint(tmp_path)) == 64
    before = cli._component_fingerprint(tmp_path)
    (tmp_path / "admin" / "StatusBadge.tsx").write_text("export default function Badge(){return null}")
    assert cli._component_fingerprint(tmp_path) != before
    with pytest.raises(RuntimeError, match="already exist"):
        cli.init_ui(tmp_path)
    (tmp_path / "pyntral.components.json").write_text(json.dumps({"fields": {"bad": "../secret.tsx"}}))
    with pytest.raises(ValueError, match="under project"):
        cli._component_fingerprint(tmp_path)


def test_env_setup(tmp_path, monkeypatch):
    values = iter(["correct-horse-battery", "correct-horse-battery"])
    monkeypatch.setattr("getpass.getpass", lambda _: next(values))
    cli.init_env(tmp_path, "admin")
    content = (tmp_path / ".env").read_text()
    assert "ADMIN_PASSWORD_HASH=scrypt$" in content
    assert "APP_SECRET_KEY=" in content
    assert "ADMIN_SECURE_COOKIE=false" in content
    with pytest.raises(RuntimeError):
        cli.init_env(tmp_path, "admin")


def test_npm_executable_windows(monkeypatch):
    monkeypatch.setattr(cli.sys, "platform", "win32")
    requested = []

    def fake_which(name):
        requested.append(name)
        return r"C:\Program Files\nodejs\npm.cmd"

    monkeypatch.setattr(cli.shutil, "which", fake_which)
    assert cli._npm_executable() == r"C:\Program Files\nodejs\npm.cmd"
    assert requested == ["npm.cmd"]


def test_windows_install_build_use_npm_cmd_and_dev_runs_vite_directly(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.sys, "platform", "win32")
    monkeypatch.setattr(cli.shutil, "which", lambda name: rf"C:\Program Files\nodejs\{name}")
    monkeypatch.setattr(cli.subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200, raising=False)
    ui = cli.sync_ui(tmp_path)
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if "install" in command or "ci" in command:
            for package in ("vite", "typescript", "@types/react", "@types/react-dom", "lucide-react"):
                (ui / "node_modules" / package).mkdir(parents=True, exist_ok=True)
        if "build" in command:
            dist = tmp_path / ".pyntral" / "dist"
            dist.mkdir(parents=True, exist_ok=True)
            (dist / "index.html").write_text("<html></html>")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    cli.install_frontend(tmp_path, ui)
    cli.build(tmp_path)
    assert len(commands) == 2
    assert all(command[0].endswith("npm.cmd") for command in commands)

    class FakeProcess:
        returncode = 0

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            return self.returncode

    vite = ui / "node_modules" / "vite" / "bin" / "vite.js"
    vite.parent.mkdir(parents=True, exist_ok=True)
    vite.write_text("")

    def fake_popen(command, **kwargs):
        assert kwargs["creationflags"] == 0x200
        commands.append(command)
        return FakeProcess()

    monkeypatch.setattr(cli, "install_frontend", lambda *_: None)
    monkeypatch.setattr(cli, "generate_types", lambda *_: None)
    monkeypatch.setattr(cli.subprocess, "Popen", fake_popen)
    assert cli.dev(tmp_path, "examples.shop.app:app", backend_port=8000,
                   frontend_port=5173, base="/admin/") == 0
    assert commands[-1][0].endswith("node.exe")
    assert Path(commands[-1][1]) == vite
    assert "--strictPort" in commands[-1]
    assert "--reload" not in commands[-2]


def test_dialog_profile_build_fingerprint(tmp_path):
    (tmp_path / "admin").mkdir()
    dialog = tmp_path / "admin" / "Dialog.tsx"
    menu = tmp_path / "admin" / "Menu.tsx"
    dialog.write_text("export default function Dialog(){return null}")
    menu.write_text("export default function Menu(){return null}")
    (tmp_path / "pyntral.components.json").write_text(json.dumps({
        "dialogs": {"confirm": "admin/Dialog.tsx"},
        "profile": {"menu": "admin/Menu.tsx"},
    }))
    before = cli._component_fingerprint(tmp_path)
    dialog.write_text("export default function Dialog(){return 'updated'}")
    assert cli._component_fingerprint(tmp_path) != before
    before = cli._component_fingerprint(tmp_path)
    menu.write_text("export default function Menu(){return 'changed'}")
    assert cli._component_fingerprint(tmp_path) != before


def test_frontend_install_manifest_cache(tmp_path, monkeypatch):
    ui = cli.sync_ui(tmp_path)
    commands = []
    def run(cmd, **kwargs):
        commands.append(cmd)
        for package in ("vite", "typescript", "@types/react", "@types/react-dom", "lucide-react"):
            (ui / "node_modules" / package).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cli.subprocess, "run", run)
    monkeypatch.setattr(cli, "_npm_executable", lambda: "npm")
    cli.install_frontend(tmp_path, ui)
    cli.install_frontend(tmp_path, ui)
    assert len(commands) == 1
    manifest = ui / "package.json"
    manifest.write_text(manifest.read_text() + " ")
    cli.install_frontend(tmp_path, ui)
    assert len(commands) == 2


def test_dev_keeps_uvicorn_level_independent_from_admin_level(tmp_path, monkeypatch):
    commands = []

    class FakeProcess:
        returncode = 0
        def poll(self):
            return 0
        def wait(self, timeout=None):
            return 0

    def fake_popen(command, *, env, **kwargs):
        commands.append((command, env))
        return FakeProcess()

    monkeypatch.setattr(cli, "generate_types", lambda *_: None)
    monkeypatch.setattr(cli, "install_frontend", lambda *_: None)
    monkeypatch.setattr(cli.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(cli, "_vite_dev_command", lambda *_: ["node", "vite.js"])
    assert cli.dev(tmp_path, "examples.shop.app:app", backend_port=8000, frontend_port=5173,
                   base="/admin/", log_level="DEBUG", uvicorn_log_level="WARNING") == 0
    cmd, env = commands[0]
    index = cmd.index("--log-level")
    assert cmd[index + 1] == "warning"
    assert "--no-access-log" in cmd
    assert env["PYNTRAL_LOG_LEVEL"] == "DEBUG"
    assert len(commands) == 2

    with pytest.raises(ValueError, match="Uvicorn log level"):
        cli.dev(tmp_path, "examples.shop.app:app", backend_port=8000, frontend_port=5173,
                base="/admin/", uvicorn_log_level="LOUD")

def test_export_ui_copies_only_compiled_assets(tmp_path):
    source = tmp_path / ".pyntral" / "dist"
    with pytest.raises(RuntimeError, match="run pyntral build"):
        cli.export_ui(tmp_path, tmp_path / "release")
    (source / "assets").mkdir(parents=True)
    (source / "index.html").write_text("<html/>")
    (source / "assets" / "app.js").write_text("export {}")
    destination = cli.export_ui(tmp_path, tmp_path / "release")
    assert (destination / "assets" / "app.js").is_file()
    with pytest.raises(ValueError, match="absent or empty"):
        cli.export_ui(tmp_path, destination)
    with pytest.raises(ValueError, match="separate"):
        cli.export_ui(tmp_path, source / "nested")
