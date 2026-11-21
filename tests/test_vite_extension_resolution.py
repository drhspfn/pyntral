"""Protect the managed workspace aliases used by host-owned UI extensions."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "src/pyntral/ui/vite.config.ts"


def test_managed_npm_dependencies_are_aliased_for_external_components():
    source = CONFIG.read_text(encoding="utf-8")
    assert 'path.join(managedUi, "package.json")' in source
    assert 'path.join(managedUi, "node_modules", dependency)' in source
    assert "...managedAliases" in source
    assert "...Object.entries({" in source
    assert source.index("...Object.entries({") < source.index("...managedAliases")
