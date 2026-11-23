"""Developer type workflow and npm release contract tests."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from pyntral import cli
from pyntral.typegen import configure_editor, generate_types

ROOT = Path(__file__).resolve().parents[1]


def test_editor_typescript_config(tmp_path):
    (tmp_path / "admin").mkdir()
    (tmp_path / "admin" / "Dashboard.tsx").write_text("export default function Dashboard() { return null; }")
    (tmp_path / "pyntral.components.json").write_text(json.dumps({
        "pages": {"dash": "admin/Dashboard.tsx"}
    }))
    root_config = configure_editor(tmp_path)
    assert json.loads(root_config.read_text())["extends"] == "./.pyntral/tsconfig.editor.json"
    editor_config = json.loads((tmp_path / ".pyntral/tsconfig.editor.json").read_text())
    assert editor_config["compilerOptions"]["paths"]["@pyntral/generated"] == ["./generated/bridges.ts"]
    assert "../admin/Dashboard.tsx" in editor_config["include"]
    root_config.write_text('{"extends":"custom.json"}\n')
    assert configure_editor(tmp_path) == root_config
    assert root_config.read_text() == '{"extends":"custom.json"}\n'


def test_editor_config_rejects_traversal(tmp_path):
    (tmp_path / "pyntral.components.json").write_text(json.dumps({
        "pages": {"bad": "../untrusted.tsx"}
    }))
    with pytest.raises(ValueError, match="outside"):
        configure_editor(tmp_path)


def test_type_generation_out_and_no_rewrite(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from pyntral import typegen

    fake_app = SimpleNamespace(state=SimpleNamespace(pyntral=SimpleNamespace(bridges={})))
    monkeypatch.setattr(typegen.importlib, "import_module", lambda _: SimpleNamespace(app=fake_app))
    out = Path("admin/generated/bridges.ts")
    assert generate_types(tmp_path, "fake:app", out=out) == (tmp_path / out).resolve()
    assert (tmp_path / ".pyntral/generated/bridges.ts").exists()
    before = (tmp_path / out).stat().st_mtime_ns
    generate_types(tmp_path, "fake:app", out=out)
    assert (tmp_path / out).stat().st_mtime_ns == before
    with pytest.raises(ValueError, match="inside"):
        generate_types(tmp_path, "fake:app", out=Path("../outside.ts"))


def test_python_source_snapshot_ignores_cache(tmp_path):
    (tmp_path / "app.py").write_text("a = 1")
    (tmp_path / ".pyntral").mkdir()
    (tmp_path / ".pyntral" / "cache.py").write_text("x = 0")
    snapshot = cli._python_source_state(tmp_path)
    assert len(snapshot) == 1
    (tmp_path / "app.py").write_text("a = 12")
    assert cli._python_source_state(tmp_path) != snapshot


def test_release_scripts_and_workflows():
    script = ROOT / "scripts/build_release.py"
    assert script.exists()
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "types: [labeled, synchronize]" in ci
    assert "github.event.label.name == 'Run checks'" in ci
    assert "contains(github.event.pull_request.labels.*.name, 'Run checks')" in ci
    assert "pull_request:" in ci and "  push:" not in ci
    assert "build_release.py" in ci
    publish = (ROOT / ".github/workflows/publish-pypi.yml").read_text()
    assert "id-token: write" in publish
    assert "pypa/gh-action-pypi-publish@release/v1" in publish
    assert "build_release.py" in publish
    assert not (ROOT / ".github/workflows/publish-npm.yml").exists()
    assert not (ROOT / "scripts/package_spa.py").exists()


def test_python_release_embeds_only_generic_assets(tmp_path):
    import importlib.util
    import zipfile
    import tarfile
    import shutil
    import pytest

    spec = importlib.util.spec_from_file_location("build_release", ROOT / "scripts/build_release.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    dist = tmp_path / "spa"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>spa</html>")
    (dist / "assets" / "app.js").write_text("console.log('spa')")
    (dist / "assets" / "app.css").write_text("body{}")
    with pytest.raises(ValueError, match="Missing compiled"):
        module.validate_spa(tmp_path / "empty")
    source = tmp_path / "embedded"
    # Do not mutate the real checkout's embedded assets during this unit test.
    module.EMBEDDED = source
    module.embed_spa(dist)
    assert (source / "index.html").is_file()
    assert (source / "assets/app.js").is_file()
    # Second embed removes stale fingerprinted files.
    (source / "assets/old.js").write_text("old")
    module.embed_spa(dist)
    assert not (source / "assets/old.js").exists()

    artifacts = tmp_path / "dist"
    artifacts.mkdir()
    with zipfile.ZipFile(artifacts / "pyntral-1.0.0b1-py3-none-any.whl", "w") as z:
        for file in source.rglob("*"):
            if file.is_file():
                z.write(file, "pyntral/web_dist/" + str(file.relative_to(source)))
    with tarfile.open(artifacts / "pyntral-1.0.0b1.tar.gz", "w:gz") as z:
        for file in source.rglob("*"):
            if file.is_file():
                z.add(file, "pyntral-1.0.0b1/src/pyntral/web_dist/" + str(file.relative_to(source)))
    module.verify_artifacts(artifacts)
