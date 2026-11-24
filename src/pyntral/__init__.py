"""Composable FastAPI + SQLAlchemy admin backend with a React SPA."""

from .admin import Admin
from .login import LoginConfig
from .sidebar import SidebarConfig, SidebarHeader, SidebarFooter, SvgIcon, ImageIcon, IconSpec
from .hooks import ResourceHook, OperationContext
from .virtual import VirtualField
from .layout import LayoutSection
from .schema_docs import describe_resources, render_markdown, write_schema_docs
from .jobs import JobAction, JobContext, JobManager
from .features import ResourceFeature, PasswordFeature, SoftDeleteFeature, TimestampFeature, AuditFeature, UploadFeature
from .audit import AuditEntry, AuditBase
from .storage import StorageBackend, LocalStorage, S3Storage, UploadBase, UploadEntry
from .sessions import MemorySessionStore, SessionIdentity, SessionStore
from .auth import CallbackAuth, LocalAuth, ModelAuth, Principal, hash_password, verify_password
from .resources import Action, Field, FieldDependency, FileUploadConfig, FieldView, Page, Resource, NavigationGroup, Relationship, RoleAccess
from .bridge import Bridge, BridgeContext, BridgeUpload, BridgeFile
from .events import (AdminEvent, FieldRef, ResourceEvent, ResourceCreated, ResourceUpdated, ResourceDeleted,
                     ActionExecuted, CollectionActionExecuted, LoginSucceeded, LoginFailed, LogoutSucceeded, CustomEvent,
                     InMemoryEventBus, EventBus, EventTransport, DeliveryReport)
from .transports.rabbitmq import RabbitMQEventBus
from .transports.kafka import KafkaEventBus
from .logging import LoggingConfig, EventFormatter, configure_logging, forward_to_loguru, stop_logging

__all__ = [
    "LoginConfig", "SidebarConfig", "SidebarHeader", "SidebarFooter", "SvgIcon", "ImageIcon", "IconSpec",
    "describe_resources", "render_markdown", "write_schema_docs",
    "JobAction", "JobContext", "JobManager",
    "Admin", "ResourceHook", "OperationContext", "VirtualField", "LayoutSection", "ResourceFeature", "PasswordFeature", "SoftDeleteFeature", "TimestampFeature", "AuditFeature", "AuditEntry", "AuditBase", "UploadFeature", "StorageBackend", "LocalStorage", "S3Storage", "UploadBase", "UploadEntry",
    "AdminEvent", "FieldRef", "ResourceEvent", "ResourceCreated", "ResourceUpdated", "ResourceDeleted",
    "ActionExecuted", "CollectionActionExecuted", "LoginSucceeded", "LoginFailed", "LogoutSucceeded", "CustomEvent",
    "InMemoryEventBus", "EventBus", "EventTransport", "DeliveryReport",
    "RabbitMQEventBus", "KafkaEventBus",
    "LoggingConfig",
    "EventFormatter",
    "configure_logging",
    "forward_to_loguru",
    "stop_logging",
    "Action",
    "Bridge",
    "BridgeContext", "BridgeUpload", "BridgeFile",
    "NavigationGroup",
    "CallbackAuth",
    "Field", "FieldDependency", "FileUploadConfig", "FieldView",
    "LocalAuth",
    "ModelAuth",
    "MemorySessionStore", "SessionIdentity", "SessionStore",
    "Page",
    "Principal",
    "Resource",
    "Relationship",
    "RoleAccess",
    "hash_password",
    "verify_password",
]
