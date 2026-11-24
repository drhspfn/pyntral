"""Release contracts: package identity, documentation navigation, and clean branding."""

from pathlib import Path
import re
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_public_identity():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["name"] == "pyntral"
    from json import loads

    version = metadata["project"]["version"]
    assert version == "1.0.0b3"
    assert loads((ROOT / "src/pyntral/ui/package.json").read_text(encoding="utf-8"))["version"] == version.replace("b", "-beta.")
    assert f"## {version} — Third public beta" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert metadata["project"]["scripts"]["pyntral"] == "pyntral.cli:main"
    assert (ROOT / "src/pyntral/__init__.py").is_file()
    assert (ROOT / "pyntral.components.json").is_file()


def test_all_markdown_relative_links_exist():
    files = [ROOT / "README.md", *ROOT.glob("docs/*.md"),
             *ROOT.glob("examples/*/README.md"),
             ROOT / "CHANGELOG.md", ROOT / "CONTRIBUTING.md", ROOT / "SECURITY.md"]
    assert len(files) >= 15
    for p in files:
        content = p.read_text(encoding="utf-8")
        for match in re.finditer(r"(?<!\!)\[[^\]]+\]\(([^)]+)\)", content):
            link = match.group(1).split("#", 1)[0]
            if not link or link.startswith(("https://", "http://", "mailto:")):
                continue
            assert (p.parent / link).exists(), f"{p.relative_to(ROOT)}: missing {link}"


def test_public_entrypoints_and_examples_are_documented():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    cli_docs = (ROOT / "docs/cli.md").read_text(encoding="utf-8")
    example = (ROOT / "examples/shop/app.py").read_text(encoding="utf-8")
    assert "# Pyntral" in readme
    assert "uv run pyntral dev" in readme
    assert "pyntral dev" in cli_docs
    assert "from pyntral import" in example
    assert (ROOT / "docs/events.md").is_file()


def test_frontend_build_dependencies_and_docker_smoke_are_packaged():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    ui = root / "src" / "pyntral" / "ui"
    manifest = json.loads((ui / "package.json").read_text())
    config = json.loads((ui / "tsconfig.json").read_text())
    assert "@types/react" in manifest["devDependencies"]
    assert "@types/react-dom" in manifest["devDependencies"]
    assert "lucide-react" in manifest["dependencies"]
    assert "eslint" in manifest["devDependencies"]
    assert "npm run check" in manifest["scripts"]["build"]
    assert "@types/react" in config["compilerOptions"]["paths"]["react"][0]
    assert (root / "examples/shop/Dockerfile").is_file()
    assert (root / "examples/shop/compose.yaml").is_file()
    assert (root / "examples/shop/Dockerfile.dockerignore").is_file()
