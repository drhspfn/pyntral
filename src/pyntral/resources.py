"""Declarative public API; SQLAlchemy metadata is resolved when a Resource is registered."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Callable, Generic, TypeVar
from uuid import UUID
from pydantic import BaseModel

from sqlalchemy.orm.attributes import InstrumentedAttribute

from sqlalchemy.orm import DeclarativeBase
from .hooks import ResourceHook
from .virtual import VirtualField
from .layout import LayoutSection
from .jobs import JobAction


@dataclass(slots=True)
class FieldView:
    """Context-specific presentation override; None inherits the base Field value.

    Per-view visibility is a presentation control, not a way to bypass
    Field.visible=False or backend role permissions.
    """
    visible: bool | None = None
    readonly: bool | None = None
    required: bool | None = None
    component: str | None = None
    order: int | None = None
    operators: list[str] | None = None  # Only meaningful for filter view


@dataclass(slots=True)
class FieldDependency:
    """Load input options through an authenticated Pydantic Bridge.

    The bridge accepts the source field under its own name, and must return
    ``{"options": [{"value": ..., "label": ...}, ...]}``. The UI relationship
    is not a security boundary: validate values again in the write handler.
    """
    source: str
    bridge: str

    def __post_init__(self) -> None:
        import re
        if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]*", self.source):
            raise ValueError("FieldDependency.source must be an attribute name")
        if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]*", self.bridge):
            raise ValueError("FieldDependency.bridge must be a registered bridge slug")


@dataclass(slots=True)
class FileUploadConfig:
    """Declarative client-side selection; no binary body or signed URL is sent.

    This first version is mock-only. Real uploads must be implemented explicitly
    by the host using an authenticated, scoped upload session and finalization.
    """
    multiple: bool = True
    max_files: int = 10
    max_size_bytes: int = 10 * 1024 * 1024
    max_total_bytes: int = 50 * 1024 * 1024
    accept: str = "image/png,image/jpeg,image/webp,application/pdf"
    preview: bool = True
    allow_paste: bool = True
    mock_only: bool = True

    def __post_init__(self) -> None:
        if not self.mock_only:
            raise ValueError("FileUploadConfig only supports mock_only=True until backend upload finalization exists")
        if type(self.max_files) is not int or not 1 <= self.max_files <= 50:
            raise ValueError("max_files must be between 1 and 50")
        if type(self.max_size_bytes) is not int or not 1 <= self.max_size_bytes <= 100 * 1024 * 1024:
            raise ValueError("max_size_bytes must be between 1 and 104857600")
        if type(self.max_total_bytes) is not int or not 1 <= self.max_total_bytes <= 200 * 1024 * 1024:
            raise ValueError("max_total_bytes must be between 1 and 209715200")
        if self.max_total_bytes < self.max_size_bytes:
            raise ValueError("max_total_bytes must not be smaller than max_size_bytes")
        if not isinstance(self.accept, str) or len(self.accept) > 512 or any(
            not item.strip() or not re.fullmatch(r"(?:\.[A-Za-z0-9+_-]{1,20}|[A-Za-z0-9.+_-]+/(?:\*|[A-Za-z0-9.+_-]+))", item.strip())
            for item in self.accept.split(",")
        ):
            raise ValueError("accept must be a comma-delimited list of MIME types or extensions")

@dataclass(slots=True)
class Field:
    label: str | None = None
    visible: bool = True
    readonly: bool = False
    required: bool | None = None
    widget: str | None = None
    file_upload: FileUploadConfig | None = None
    help: str | None = None
    options: list[dict[str, Any]] | list[str] | None = None
    components: dict[str, str] = field(default_factory=dict)  # {list: id, edit: id, show: id}
    span: int = 1  # Full row when 2 in a two-column layout
    read_role: str | None = None  # Optional minimum role for this field
    write_role: str | None = None  # Optional minimum role to modify this field
    read_when: Callable[[Any, Any | None], Any] | None = None  # (principal, record) -> bool
    write_when: Callable[[Any, Any | None], Any] | None = None
    filter_operators: list[str] | None = None  # Restrict supported filter operations for this field
    filter_width: int | None = None  # Optional filter control width in px; auto-sized otherwise
    dependency: FieldDependency | None = None
    list: FieldView | None = None
    edit: FieldView | None = None
    create: FieldView | None = None
    show: FieldView | None = None
    filter: FieldView | None = None

    def __post_init__(self) -> None:
        if self.file_upload is not None and not isinstance(self.file_upload, FileUploadConfig):
            raise TypeError("file_upload must be FileUploadConfig")
        if self.span not in (1, 2):
            raise ValueError("Field.span must be 1 or 2")
        if self.filter_width is not None and (
            type(self.filter_width) is not int or not 140 <= self.filter_width <= 560
        ):
            raise ValueError("Field.filter_width must be between 140 and 560 pixels")


@dataclass(slots=True)
class Action:
    name: str
    handler: Callable[..., Any]
    label: str | None = None
    variant: str = "secondary"
    confirmation: str | None = None
    position: str = "both"  # row | detail | both
    appearance: str = "button"  # button | badge | menu
    component: str | None = None  # React extension action ID; opens an action page
    dialog: str | None = None  # React extension dialog body, shown before invoking the action
    icon: str | None = None
    visible: bool | Callable[..., Any] = True  # (principal, record) -> bool, async supported
    kind: str = "record"  # record | bulk | resource

    def __post_init__(self) -> None:
        if self.kind not in ("record", "bulk", "resource"):
            raise ValueError("Action kind must be record, bulk or resource")
        if self.position not in ("row", "detail", "both"):
            raise ValueError("Action position must be row, detail or both")
        if self.appearance not in ("button", "badge", "menu"):
            raise ValueError("Action appearance must be button, badge or menu")


@dataclass(slots=True)
class NavigationGroup:
    path: str  # e.g. "Agents" or "Agents/Runtime"
    icon: str = "folder"
    order: int = 0


@dataclass(slots=True)
class RoleAccess:
    """Minimum role thresholds per operation; an omitted write role denies writes.

    Only applies to a Resource when explicitly provided. ``select`` defaults to
    ``read``; ``create`` / ``edit`` / ``delete`` default to ``write``.
    Unknown role names fail closed. Role hierarchy is configured on Admin.
    """
    read: str | None = None
    select: str | None = None
    write: str | None = None
    create: str | None = None
    edit: str | None = None
    delete: str | None = None
    navigation: str = "hide"  # hide | lock

    def __post_init__(self) -> None:
        if self.navigation not in ("hide", "lock"):
            raise ValueError("RoleAccess.navigation must be hide or lock")

    def threshold(self, action: str) -> str | None:
        if action == "select":
            return self.select if self.select is not None else self.read
        if action in ("list", "show"):
            return self.read
        if action in ("create", "edit", "delete"):
            return getattr(self, action) or self.write
        # Custom actions require write permission plus their own authorize callback.
        if action.startswith("action:"):
            return self.write
        return None


@dataclass(slots=True)
class Page:
    name: str
    label: str
    component: str  # registered React component ID
    icon: str = "layout-dashboard"
    navigation: str | None = None
    navigation_order: int = 0
    min_role: str | None = None


@dataclass(slots=True)
class Relationship:
    """Presentation of a mapped SQLAlchemy relationship (not its FK column)."""
    visible: bool = True
    label: str | None = None
    selectable: bool = False  # Enable selection/search in the related list
    layout: str = "table"  # table | cards

    def __post_init__(self) -> None:
        if self.layout not in ("table", "cards"):
            raise ValueError("Relationship.layout must be table or cards")


ModelT = TypeVar("ModelT", bound=DeclarativeBase)


@dataclass(slots=True)
class Resource(Generic[ModelT]):
    model: type[ModelT]
    name: str | None = None
    label: str | None = None
    icon: str = "database"
    navigation: str | None = None
    navigation_order: int = 0
    list_fields: list[str] | None = None
    search_fields: list[str] = field(default_factory=list)
    show_search: bool = False  # Optional quick search above the advanced filters
    fields: dict[str, Field] = field(default_factory=dict)
    actions: list[Action] = field(default_factory=list)
    jobs: list[JobAction] = field(default_factory=list)
    page_size: int = 20
    title_field: str | None = None  # String field name; use visible_name for static typing
    visible_name: InstrumentedAttribute[str] | InstrumentedAttribute[int] | InstrumentedAttribute[UUID] | None = None
    label_factory: Callable[[ModelT], str] | None = None  # Row-based display label; no SQL search for computed labels
    relationships: dict[str, Relationship] = field(default_factory=dict)
    form_layout: str = "stack"  # stack | grid
    detail_layout: str = "stack"  # stack | grid
    crud_views: dict[str, str] = field(default_factory=dict)  # list/create/edit/show -> extension ID
    hooks: list[ResourceHook] = field(default_factory=list)
    virtual_fields: dict[str, VirtualField] = field(default_factory=dict)
    create_schema: type[BaseModel] | None = None
    edit_schema: type[BaseModel] | None = None
    version_field: str | None = None  # Requires SQLAlchemy mapper.version_id_col
    form_sections: list[LayoutSection] = field(default_factory=list)
    detail_sections: list[LayoutSection] = field(default_factory=list)
    features: list[Any] = field(default_factory=list)  # ResourceFeature protocol; applied on registration
    _features_applied: bool = field(default=False, init=False, repr=False)
    _server_defaults: dict[str, Callable[[], Any]] = field(default_factory=dict, init=False, repr=False)
    _server_onupdate: dict[str, Callable[[], Any]] = field(default_factory=dict, init=False, repr=False)
    _audit_enabled: bool = field(default=False, init=False, repr=False)
    _uploads_enabled: bool = field(default=False, init=False, repr=False)
    _upload_max_bytes: int = field(default=10_485_760, init=False, repr=False)
    scope: Callable[..., Any] | None = None  # (principal, SELECT) -> SELECT
    operation_policy: Callable[[Any, str, Any | None], Any] | None = None
    access: RoleAccess | None = None
    allow_create: bool = True
    allow_edit: bool = True
    allow_delete: bool = True
    allow_show: bool = True

    def __post_init__(self) -> None:
        action_names = [action.name for action in self.actions] + [action.name for action in self.jobs]
        if len(action_names) != len(set(action_names)):
            raise ValueError("Job and action names must be distinct")
        for schema in (self.create_schema, self.edit_schema):
            if schema is not None and (not isinstance(schema, type) or not issubclass(schema, BaseModel)):
                raise TypeError("create_schema and edit_schema must inherit Pydantic BaseModel")
        if self.form_layout not in ("stack", "grid") or self.detail_layout not in ("stack", "grid"):
            raise ValueError("Layout must be stack or grid")
        if any(k not in {"list", "create", "edit", "show"} or not v or not isinstance(v, str)
               for k, v in self.crud_views.items()):
            raise ValueError("crud_views must map list/create/edit/show to component IDs")
        if self.page_size < 1 or self.page_size > 200:
            raise ValueError("page_size must be between 1 and 200")
        if self.name is None:
            import re

            name = re.sub(r"(?<!^)(?=[A-Z])", "_", self.model.__name__).lower()
            self.name = name.replace("_", "-") + "s"
        if self.label is None:
            self.label = self.model.__name__ + "s"


def validate_navigation(path: str | None) -> None:
    if path is None:
        return
    if not isinstance(path, str) or not path or any(not part.strip() for part in path.split("/")):
        raise ValueError("Navigation must be a non-empty slash-separated group path")
    if len(path) > 200 or any(c in path for c in ("\\", "\n", "\r")):
        raise ValueError("Invalid navigation path")
