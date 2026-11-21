"""Static source/distribution contract tests (do not require npm registry access)."""

import json
from pathlib import Path

from pyntral import cli


ROOT = Path(__file__).resolve().parents[1]


def test_frontend_contract():
    ui = cli._source_ui()
    deps = json.loads((ui / "package.json").read_text())
    assert deps["dependencies"]["react"].startswith("19.")
    assert deps["devDependencies"]["vite"].startswith("8.")
    tsconfig = json.loads((ui / "tsconfig.json").read_text())
    assert "baseUrl" not in tsconfig["compilerOptions"]  # removed in TypeScript 7
    assert "@pyntral/types" in tsconfig["compilerOptions"]["paths"]
    assert "@pyntral/api" in tsconfig["compilerOptions"]["paths"]
    assert (ui / "src" / "App.tsx").is_file()
    assert (ui / "src" / "virtual.d.ts").is_file()


def test_example_extensions_registered():
    config = json.loads((ROOT / "pyntral.components.json").read_text())
    assert config["fields"]["order-status"] == "admin/OrderStatusBadge.tsx"
    assert config["pages"]["insights"] == "admin/Insights.tsx"
    assert (ROOT / "admin" / "OrderStatusBadge.tsx").is_file()
    assert (ROOT / "admin" / "Insights.tsx").is_file()
    assert len(cli._component_fingerprint(ROOT)) == 64
