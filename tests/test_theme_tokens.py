"""Theme token audit for built-in styles (not consumer extensions)."""
import re
from pathlib import Path


def test_builtin_component_colors_use_theme_tokens():
    css = (Path(__file__).resolve().parents[1] /
           "src/pyntral/ui/src/style.css").read_text(encoding="utf-8")
    component_rules = css.split("* {box-sizing:border-box}", 1)[1]
    assert not re.search(r"#[a-fA-F0-9]{3,8}\\b|\\brgba?\\(", component_rules)
    for name in ("on-primary", "mobile-backdrop", "modal-backdrop",
                 "dialog-shadow", "popup-shadow", "select-shadow",
                 "calendar-shadow", "filter-shadow", "settings-shadow"):
        assert f"--ra-{name}:" in css
        assert f"var(--ra-{name})" in component_rules
