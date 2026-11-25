"""Read-only field presentation settings; never change write or read permissions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

BadgeTone = Literal["neutral", "primary", "success", "danger", "warning"]
_TONES = {"neutral", "primary", "success", "danger", "warning"}


@dataclass(frozen=True, slots=True)
class StatusBadgeConfig:
    """Opt-in status badge, with exact-value overrides and a neutral unknown fallback."""
    tones: dict[str, BadgeTone] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    default_tone: BadgeTone = "neutral"
    auto_tone: bool = True
    dot: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.tones, dict) or any(not isinstance(k, str) or not isinstance(v, str) or v not in _TONES for k, v in self.tones.items()):
            raise ValueError("StatusBadgeConfig.tones must map strings to badge tones")
        if not isinstance(self.labels, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in self.labels.items()):
            raise ValueError("StatusBadgeConfig.labels must map strings to labels")
        if self.default_tone not in _TONES or type(self.auto_tone) is not bool or type(self.dot) is not bool:
            raise ValueError("Invalid status badge configuration")

    def metadata(self) -> dict:
        return {"tones": dict(self.tones), "labels": dict(self.labels),
                "defaultTone": self.default_tone, "autoTone": self.auto_tone, "dot": self.dot}


@dataclass(frozen=True, slots=True)
class CodeFieldConfig:
    """CodeBlock presentation in details, optional inline list preview and multiline edit."""
    language: str = "auto"
    highlight: bool = True
    highlight_toggle: bool = False
    format: bool = True
    format_toggle: bool = True
    copyable: bool = True
    collapsible: bool = True
    default_collapsed: bool = False
    wrap: bool = False
    max_height: int = 360
    list_inline: bool = False
    edit_rows: int = 6

    def __post_init__(self) -> None:
        if not isinstance(self.language, str) or not self.language.strip() or len(self.language) > 40:
            raise ValueError("Invalid code language")
        if any(type(value) is not bool for value in (
            self.highlight, self.highlight_toggle, self.format, self.format_toggle, self.copyable,
            self.collapsible, self.default_collapsed, self.wrap, self.list_inline,
        )):
            raise ValueError("CodeFieldConfig switches must be boolean")
        if type(self.max_height) is not int or not 40 <= self.max_height <= 2000:
            raise ValueError("CodeFieldConfig.max_height must be 40–2000 pixels")
        if type(self.edit_rows) is not int or not 2 <= self.edit_rows <= 50:
            raise ValueError("CodeFieldConfig.edit_rows must be 2–50")

    def metadata(self) -> dict:
        return {"language": self.language, "highlight": self.highlight,
                "highlightToggle": self.highlight_toggle, "format": self.format,
                "formatToggle": self.format_toggle, "copyable": self.copyable,
                "collapsible": self.collapsible, "defaultCollapsed": self.default_collapsed,
                "wrap": self.wrap, "maxHeight": self.max_height, "listInline": self.list_inline,
                "editRows": self.edit_rows}
