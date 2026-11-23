"""Public presentation-only configuration for the unauthenticated login screen."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .sidebar import IconSpec, SidebarHeader, icon_metadata


@dataclass(frozen=True, slots=True)
class LoginConfig:
    layout: Literal["centered", "split"] = "centered"
    side_position: Literal["left", "right"] = "left"
    brand_position: Literal["auto", "form", "side", "hidden"] = "auto"
    brand: SidebarHeader | None = None  # inherit the sidebar brand by default
    brand_align: Literal["left", "center", "right"] | None = None
    brand_direction: Literal["horizontal", "vertical"] | None = None
    form_align: Literal["left", "center", "right"] = "center"
    card: bool = True
    max_width: int = 420
    title: str = "Sign in"
    subtitle: str | None = "Use your administrator account to continue."
    eyebrow: str | None = None
    form_icon: IconSpec = None
    username_label: str = "Username"
    password_label: str = "Password"
    submit_label: str = "Continue"
    footer: str | None = None
    side_title: str | None = None
    side_description: str | None = None
    side_footer: str | None = None
    show_theme_toggle: bool = True
    show_password_toggle: bool = True

    def __post_init__(self) -> None:
        if self.layout not in ("centered", "split") or self.side_position not in ("left", "right"):
            raise ValueError("Invalid login layout or side position")
        if self.brand_position not in ("auto", "form", "side", "hidden"):
            raise ValueError("Invalid login brand position")
        if self.brand_position == "side" and self.layout != "split":
            raise ValueError("Side branding requires the split login layout")
        if self.form_align not in ("left", "center", "right") or self.brand_align not in (None, "left", "center", "right"):
            raise ValueError("Invalid login alignment")
        if self.brand_direction not in (None, "horizontal", "vertical"):
            raise ValueError("Invalid login brand direction")
        if type(self.max_width) is not int or not 280 <= self.max_width <= 640:
            raise ValueError("Login max_width must be 280–640 pixels")
        if self.brand is not None and not isinstance(self.brand, SidebarHeader):
            raise TypeError("Login brand must be SidebarHeader or None")
        for label in (self.title, self.username_label, self.password_label, self.submit_label):
            if not isinstance(label, str) or not label.strip():
                raise ValueError("Login title and field/button labels must be non-empty strings")
        for text in (self.subtitle, self.eyebrow, self.footer, self.side_title,
                     self.side_description, self.side_footer):
            if text is not None and not isinstance(text, str):
                raise TypeError("Optional login text must be a string or None")
        for flag in (self.card, self.show_theme_toggle, self.show_password_toggle):
            if type(flag) is not bool:
                raise TypeError("Login visibility flags must be booleans")
        icon_metadata(self.form_icon)

    def metadata(self, title: str, sidebar_header: SidebarHeader | None) -> dict:
        position = self.brand_position
        if position == "auto":
            position = "side" if self.layout == "split" else "form"
        brand = (self.brand or sidebar_header or SidebarHeader()).metadata(title)
        brand["align"] = self.brand_align or ("left" if position == "side" else self.form_align)
        brand["direction"] = self.brand_direction or ("horizontal" if position == "side" else "vertical")
        return {"layout": self.layout, "sidePosition": self.side_position,
                "brandPosition": position, "brand": brand if position != "hidden" else None,
                "formAlign": self.form_align, "card": self.card, "maxWidth": self.max_width,
                "title": self.title, "subtitle": self.subtitle, "eyebrow": self.eyebrow,
                "formIcon": icon_metadata(self.form_icon), "usernameLabel": self.username_label,
                "passwordLabel": self.password_label, "submitLabel": self.submit_label,
                "footer": self.footer, "sideTitle": self.side_title,
                "sideDescription": self.side_description, "sideFooter": self.side_footer,
                "showThemeToggle": self.show_theme_toggle, "showPasswordToggle": self.show_password_toggle}
