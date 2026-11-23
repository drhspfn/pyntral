"""Declarative icon and sidebar presentation. No frontend build is needed for these settings."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
import re
import xml.etree.ElementTree as ET


@dataclass(frozen=True, slots=True)
class SvgIcon:
    """SVG rendered in an isolated image context, never inserted as DOM markup."""
    svg: str

    def __post_init__(self) -> None:
        if not isinstance(self.svg, str) or len(self.svg.encode("utf-8")) > 128 * 1024:
            raise ValueError("SVG icon must be at most 128 KiB")
        if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", self.svg, re.IGNORECASE):
            raise ValueError("SVG declarations and entities are not allowed")
        try:
            root = ET.fromstring(self.svg)
        except ET.ParseError as exc:
            raise ValueError("Invalid SVG icon") from exc
        if root.tag not in ("svg", "{http://www.w3.org/2000/svg}svg"):
            raise ValueError("Expected an SVG root element")

    @classmethod
    def from_file(cls, path: str | Path) -> SvgIcon:
        return cls(Path(path).read_text(encoding="utf-8"))


def _validate_image_url(value: str) -> None:
    if not isinstance(value, str) or not value or len(value) > 2048 or re.search(r"[\x00-\x20\\]", value):
        raise ValueError("Invalid image icon URL")
    parsed = urlsplit(value)
    if parsed.scheme not in ("", "http", "https") or value.startswith("//"):
        raise ValueError("Image icons require HTTP(S) or relative URLs")
    if parsed.scheme and (not parsed.hostname or parsed.username or parsed.password):
        raise ValueError("Invalid image icon URL")


@dataclass(frozen=True, slots=True)
class ImageIcon:
    src: str | None = None
    light: str | None = None
    dark: str | None = None

    def __post_init__(self) -> None:
        if not any((self.src, self.light, self.dark)):
            raise ValueError("ImageIcon requires src, light or dark")
        for value in (self.src, self.light, self.dark):
            if value is not None:
                _validate_image_url(value)


IconSpec = str | SvgIcon | ImageIcon | None


def icon_metadata(icon: IconSpec) -> str | dict | None:
    if icon is None:
        return None
    if isinstance(icon, str):
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", icon) or len(icon) > 100:
            raise ValueError("Lucide icon names must be lowercase kebab-case")
        return icon
    if isinstance(icon, SvgIcon):
        return {"kind": "svg", "svg": icon.svg}
    if isinstance(icon, ImageIcon):
        return {"kind": "image", "src": icon.src, "light": icon.light, "dark": icon.dark}
    raise TypeError("Expected a Lucide name, SvgIcon, ImageIcon or None")


@dataclass(frozen=True, slots=True)
class SidebarHeader:
    title: str | None = None  # None inherits Admin.title
    subtitle: str | None = None
    icon: IconSpec = "command"
    show_icon: bool = True
    show_title: bool = True
    show_subtitle: bool = True
    align: Literal["left", "center", "right"] = "left"
    direction: Literal["horizontal", "vertical"] = "horizontal"
    divider: bool = True
    icon_size: int = 24
    logo_width: int | None = None
    icon_background: bool = True
    link_to_dashboard: bool = True

    def __post_init__(self) -> None:
        if self.align not in ("left", "center", "right") or self.direction not in ("horizontal", "vertical"):
            raise ValueError("Invalid sidebar header alignment or direction")
        if type(self.icon_size) is not int or not 12 <= self.icon_size <= 120:
            raise ValueError("Header icon_size must be 12–120 pixels")
        if self.logo_width is not None and (type(self.logo_width) is not int or not 12 <= self.logo_width <= 420):
            raise ValueError("Header logo_width must be 12–420 pixels")
        icon_metadata(self.icon)

    def metadata(self, title: str) -> dict:
        return {"title": title if self.title is None else self.title, "subtitle": self.subtitle,
                "icon": icon_metadata(self.icon), "showIcon": self.show_icon, "showTitle": self.show_title,
                "showSubtitle": self.show_subtitle, "align": self.align, "direction": self.direction,
                "divider": self.divider, "iconSize": self.icon_size, "logoWidth": self.logo_width,
                "iconBackground": self.icon_background, "linkToDashboard": self.link_to_dashboard}


@dataclass(frozen=True, slots=True)
class SidebarFooter:
    show_user: bool = True
    show_avatar: bool = True
    show_roles: bool = True
    divider: bool = True

    def metadata(self) -> dict:
        return {"showUser": self.show_user, "showAvatar": self.show_avatar,
                "showRoles": self.show_roles, "divider": self.divider}


@dataclass(frozen=True, slots=True)
class SidebarConfig:
    width: int = 238
    min_width: int = 238
    max_width: int = 420
    mobile_width: int = 238
    resizable: bool = True
    show_icons: bool = True
    icon_size: int = 16
    indent: int = 9
    max_indent_depth: int = 5
    dashboard_icon: IconSpec = "layout-dashboard"
    header: SidebarHeader | None = field(default_factory=SidebarHeader)
    footer: SidebarFooter | None = field(default_factory=SidebarFooter)
    header_component: str | None = None
    footer_component: str | None = None
    item_component: str | None = None

    def __post_init__(self) -> None:
        if any(type(v) is not int for v in (self.width, self.min_width, self.max_width, self.mobile_width,
                                           self.icon_size, self.indent, self.max_indent_depth)):
            raise ValueError("Sidebar dimensions must be integers")
        if not 160 <= self.min_width <= self.width <= self.max_width <= 640:
            raise ValueError("Sidebar widths must satisfy 160 <= min_width <= width <= max_width <= 640")
        if not 160 <= self.mobile_width <= 480 or not 12 <= self.icon_size <= 32:
            raise ValueError("Invalid mobile width or navigation icon size")
        if not 0 <= self.indent <= 24 or not 0 <= self.max_indent_depth <= 8:
            raise ValueError("Invalid navigation indentation")
        icon_metadata(self.dashboard_icon)
        if self.header is not None and not isinstance(self.header, SidebarHeader):
            raise TypeError("header must be SidebarHeader or None")
        if self.footer is not None and not isinstance(self.footer, SidebarFooter):
            raise TypeError("footer must be SidebarFooter or None")
        for component in (self.header_component, self.footer_component, self.item_component):
            if component is not None and (not isinstance(component, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", component)):
                raise ValueError("Invalid sidebar extension ID")

    def metadata(self, title: str) -> dict:
        return {"width": self.width, "minWidth": self.min_width, "maxWidth": self.max_width,
                "mobileWidth": self.mobile_width, "resizable": self.resizable, "showIcons": self.show_icons,
                "iconSize": self.icon_size, "indent": self.indent, "maxIndentDepth": self.max_indent_depth,
                "dashboardIcon": icon_metadata(self.dashboard_icon),
                "header": self.header.metadata(title) if self.header else None,
                "footer": self.footer.metadata() if self.footer else None,
                "headerComponent": self.header_component, "footerComponent": self.footer_component,
                "itemComponent": self.item_component}
