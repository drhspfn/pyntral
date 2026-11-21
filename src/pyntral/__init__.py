"""Composable FastAPI + SQLAlchemy admin backend with a React SPA."""

from .admin import Admin
from .hooks import ResourceHook, OperationContext
from .auth import CallbackAuth, LocalAuth, ModelAuth, Principal, hash_password, verify_password
from .resources import Action, Field, FieldView, Page, Resource, NavigationGroup, Relationship, RoleAccess
from .bridge import Bridge, BridgeContext
from .events import (AdminEvent, FieldRef, ResourceEvent, ResourceCreated, ResourceUpdated, ResourceDeleted,
                     ActionExecuted, CollectionActionExecuted, LoginSucceeded, LoginFailed, LogoutSucceeded, CustomEvent,
                     InMemoryEventBus, EventBus, EventTransport, DeliveryReport)
from .transports.rabbitmq import RabbitMQEventBus
from .transports.kafka import KafkaEventBus
from .logging import LoggingConfig, EventFormatter, configure_logging, forward_to_loguru, stop_logging

__all__ = [
    "Admin", "ResourceHook", "OperationContext",
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
    "BridgeContext",
    "NavigationGroup",
    "CallbackAuth",
    "Field", "FieldView",
    "LocalAuth",
    "ModelAuth",
    "Page",
    "Principal",
    "Resource",
    "Relationship",
    "RoleAccess",
    "hash_password",
    "verify_password",
]
