"""FastAPI integration and secured REST contract for the React frontend."""

from __future__ import annotations

import hashlib
import hmac
from copy import deepcopy
from inspect import iscoroutinefunction
import csv
import io
import asyncio
from contextlib import asynccontextmanager
import json
import re
import os
import secrets
import time
import uuid
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, unquote, urlparse

from fastapi import Depends, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from sqlalchemy import delete, inspect as sa_inspect, select, update
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.sessions import SessionMiddleware

from .auth import AuthBackend, ModelAuth, Principal, maybe_await
from .events import (
    AdminEvent, EventTransport, InMemoryEventBus, ResourceCreated, ResourceUpdated, ResourceDeleted,
    ActionExecuted, CollectionActionExecuted, LoginSucceeded, LoginFailed, LogoutSucceeded, FieldRef, field_refs, event_context,
)
from .orm import AdminError, MapperAdapter
from .resources import Page, Resource, NavigationGroup, validate_navigation
from .sidebar import SidebarConfig, icon_metadata
from .login import LoginConfig
from .hooks import OperationContext
from .realtime import RealtimeNotifier
from .jobs import JobManager
from .validation import validate_payload
from .sessions import MemorySessionStore, SessionIdentity, SessionStore
from .storage import _PENDING_DELETE_RECORD, StorageBackend, UploadEntry, safe_upload_name, normalize_mime
from .bridge import Bridge, BridgeContext, BridgeFile
from .logging import (LoggingConfig, configure_logging, emit as emit_log, request_id_var)
from pydantic import ValidationError


class Admin:
    """Mount a metadata-driven admin SPA at a configurable path.

    Args:
        app: parent FastAPI application.
        session_factory: SQLAlchemy sessionmaker (sync or AsyncSession).
        auth: required authentication backend. No unsafe implicit anonymous mode.
        secret_key: long random secret, persisted across restarts.
        secure_cookie: set True behind HTTPS; False only for local HTTP development.
    """

    def __init__(
        self,
        app: FastAPI,
        *,
        session_factory: Callable[[], Any],
        auth: AuthBackend,
        secret_key: str,
        path: str = "/admin",
        secure_cookie: bool = True,
        session_cookie: str = "pyntral_session",
        session_cookie_path: str = "/",
        session_max_age: int = 12 * 60 * 60,
        session_store: SessionStore | None = None,
        require_async_sessions: bool = False,
        enable_jobs: bool = True,
        dist_dir: str | Path | None = None,
        title: str = "Pyntral",
        theme: dict[str, Any] | None = None,
        default_theme: str = "system",  # system | light | dark
        animations: bool = True,
        show_dashboard: bool = True,
        sidebar: SidebarConfig | None = None,
        login: LoginConfig | None = None,
        role_weights: dict[str, int] | None = None,
        logging_config: LoggingConfig | None = None,
        event_bus: EventTransport | None = None,
        auto_start_events: bool = True,
        event_publish_timeout: float = 2.0,
        max_json_bytes: int = 1024 * 1024,
        storage: StorageBackend | None = None,
        default_locale: str = "en",
        translations: dict[str, dict[str, str]] | None = None,
        locale_resolver: Callable[[Principal], Any] | None = None,
        theme_resolver: Callable[[Principal], Any] | None = None,
        realtime_updates: bool = False,
    ):
        if not isinstance(secret_key, str) or len(secret_key) < 32:
            raise ValueError("secret_key must contain at least 32 characters")
        if not path.startswith("/") or path == "/" or path.endswith("/"):
            raise ValueError("path must look like /admin (no trailing slash)")
        if auth is None:
            raise ValueError("An authentication backend is required")
        if not 0 < event_publish_timeout <= 60:
            raise ValueError("event_publish_timeout must be greater than zero and at most 60 seconds")
        if type(max_json_bytes) is not int or max_json_bytes < 1:
            raise ValueError("max_json_bytes must be a positive integer")
        self.event_publish_timeout = event_publish_timeout
        self.max_json_bytes = max_json_bytes
        if type(session_max_age) is not int or session_max_age < 1:
            raise ValueError("session_max_age must be a positive integer")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", session_cookie):
            raise ValueError("session_cookie must be a valid cookie name")
        if not session_cookie_path.startswith("/") or any(c in session_cookie_path for c in ";\r\n"):
            raise ValueError("session_cookie_path must be an absolute cookie path")
        self.session_max_age = session_max_age
        self.session_store = session_store if session_store is not None else MemorySessionStore()
        self._session_audience = hashlib.sha256(f"{path}:{session_cookie}:{session_cookie_path}".encode()).hexdigest()
        self.enable_jobs = enable_jobs
        self.session_factory = session_factory
        self.storage = storage
        self._upload_cleanup_wakeup: asyncio.Event | None = None
        if re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", default_locale) is None:
            raise ValueError("default_locale must be a BCP47-like language tag")
        self.default_locale = default_locale
        self.translations = translations or {}
        self.locale_resolver = locale_resolver
        self.theme_resolver = theme_resolver
        for locale, messages in self.translations.items():
            if not isinstance(messages, dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                                      for k, v in messages.items()):
                raise ValueError(f"Translation messages for {locale} must be string mappings")
        self.auth = auth
        self.path = path
        self.title = title
        self.resources: dict[str, MapperAdapter] = {}
        self.pages: dict[str, Page] = {}
        self.groups: dict[str, NavigationGroup] = {}
        self.bridges: dict[str, Bridge] = {}
        self.events = event_bus if event_bus is not None else InMemoryEventBus()
        self.realtime = RealtimeNotifier(self.events) if realtime_updates else None
        self.jobs = JobManager()
        # Jobs must be cancelled on shutdown even if the external EventBus
        # lifecycle is controlled by the host application.
        # Mounted sub-app lifespans are not driven by Starlette. Compose the
        # existing parent lifespan and stop all jobs during shutdown.
        previous_lifespan = app.router.lifespan_context
        event_transport = self.events

        @asynccontextmanager
        async def admin_events_lifespan(host_app: FastAPI):
            async with previous_lifespan(host_app) as host_state:
                if require_async_sessions:
                    factories = [self.session_factory]
                    if isinstance(self.auth, ModelAuth):
                        factories.append(self.auth.session_factory)
                    for factory in factories:
                        session = factory()
                        try:
                            if not iscoroutinefunction(session.execute):
                                raise TypeError("require_async_sessions requires SQLAlchemy AsyncSession factories")
                        finally:
                            await maybe_await(session.close())
                if auto_start_events:
                    await event_transport.start()
                cleanup = None
                if self.storage is not None and any(adapter.resource._uploads_enabled for adapter in self.resources.values()):
                    self._upload_cleanup_wakeup = asyncio.Event()
                    cleanup = asyncio.create_task(self._upload_cleanup_loop(self._upload_cleanup_wakeup))
                try:
                    yield host_state
                finally:
                    if cleanup is not None:
                        self._upload_cleanup_wakeup = None
                        cleanup.cancel()
                        await asyncio.gather(cleanup, return_exceptions=True)
                    await self.jobs.close()
                    if auto_start_events:
                        await event_transport.close()

        app.router.lifespan_context = admin_events_lifespan
        if default_theme not in ("light", "dark", "system"):
            raise ValueError("default_theme must be system, light or dark")
        self.theme = theme or {}
        self.default_theme = default_theme
        self.animations = animations
        self.show_dashboard = show_dashboard
        if sidebar is not None and not isinstance(sidebar, SidebarConfig):
            raise TypeError("sidebar must be SidebarConfig")
        self.sidebar = sidebar if sidebar is not None else SidebarConfig()
        if login is not None and not isinstance(login, LoginConfig):
            raise TypeError("login must be LoginConfig")
        self.login_config = login if login is not None else LoginConfig()
        self.role_weights = dict(role_weights or {})
        # The CLI explicitly opts into package-owned console logging. Library use
        # never changes the host application's logging handlers implicitly.
        if os.environ.get("PYNTRAL_CLI_LOGGING") == "1":
            configure_logging(
                level=os.getenv("PYNTRAL_LOG_LEVEL", "INFO"),
                format=os.getenv("PYNTRAL_LOG_FORMAT", "compact"),
                file=os.getenv("PYNTRAL_LOG_FILE") or None,
                channel_files=json.loads(
                    os.getenv("PYNTRAL_LOG_CHANNEL_FILES", "{}")),
            )
        self.logging_config = logging_config or (
            LoggingConfig.from_environment()
            if os.environ.get("PYNTRAL_CLI_LOGGING") == "1" else LoggingConfig()
        )
        if any(not isinstance(k, str) or not isinstance(v, int) or isinstance(v, bool)
               for k, v in self.role_weights.items()):
            raise ValueError("role_weights must map role names to integer priorities")
        app.state.pyntral = self
        self.dist_dir = Path(dist_dir).resolve() if dist_dir else None
        self.api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
        self.api.add_middleware(
            SessionMiddleware,
            secret_key=secret_key,
            session_cookie=session_cookie,
            path=session_cookie_path,
            max_age=session_max_age,
            same_site="lax",
            https_only=secure_cookie,
        )
        self._register_routes()
        app.mount(path, self.api, name="pyntral")
        self.log_event("lifecycle", "admin.mounted", path=path)

    def log_event(self, channel: str, event: str, *, level: str = "INFO",
                  principal: Principal | None = None, **fields: Any) -> None:
        """Emit a structured, configurable event without leaking request payloads."""
        if principal is not None and self.logging_config.include_principal_id:
            fields["principal_id"] = principal.id
        if not self.logging_config.include_record_id:
            fields.pop("record_id", None)
        emit_log(self.logging_config, channel, event, level=level, **fields)

    async def _publish(self, event: AdminEvent) -> None:
        """Dispatch after success without turning a committed write into a 500."""
        try:
            async with asyncio.timeout(self.event_publish_timeout):
                report = await self.events.publish(event)
            self.log_event("events", "events.published", level="DEBUG",
                           event_type=event.type, event_id=event.event_id,
                           resource=event.resource, correlation_id=event.correlation_id,
                           field_names=[field.name for field in event.fields])
            if report.failed:
                self.log_event("events", "events.subscriber_failed", level="ERROR",
                               event_type=event.type, failed=report.failed)
        except TimeoutError:
            self.log_event("events", "events.publish_timed_out", level="ERROR", event_type=event.type)
        except Exception:
            # Even a custom bus must not corrupt the result of an already committed write.
            self.log_event("events", "events.dispatch_failed", level="ERROR",
                           event_type=event.type)

    @staticmethod
    async def _begin_upload_transaction(session: Any, *, write: bool) -> None:
        # SQLite ignores FOR UPDATE. Start a write transaction before reading the
        # owner for attachment mutations, or pin a consistent snapshot for reads.
        if session.get_bind().dialect.name == "sqlite":
            connection = await maybe_await(session.connection())
            sync_connection = getattr(connection, "sync_connection", connection)
            if not sync_connection.connection.driver_connection.in_transaction:
                await maybe_await(connection.exec_driver_sql("BEGIN IMMEDIATE" if write else "BEGIN"))

    async def _upload_cleanup_loop(self, wakeup: asyncio.Event) -> None:
        while True:
            wakeup.clear()
            try:
                await self._cleanup_uploads()
            except SQLAlchemyError:
                self.log_event("resource", "upload.cleanup_database_failed", level="ERROR")
            try:
                await asyncio.wait_for(wakeup.wait(), timeout=60)
            except TimeoutError:
                pass

    async def _cleanup_uploads(self) -> None:
        storage = self.storage
        if storage is None:
            return
        resources = [name for name, adapter in self.resources.items() if adapter.resource._uploads_enabled]
        pending = (UploadEntry.record_id == _PENDING_DELETE_RECORD) & UploadEntry.resource.in_(resources)
        cursor = ""
        while True:
            session = self.session_factory()
            try:
                entries = (await maybe_await(session.execute(
                    select(UploadEntry.id, UploadEntry.object_key).where(pending, UploadEntry.id > cursor)
                    .order_by(UploadEntry.id).limit(100)
                ))).all()
            finally:
                await maybe_await(session.close())
            if not entries:
                return
            cursor = entries[-1].id
            completed = []
            for upload_id, key in entries:
                try:
                    await storage.delete(key)
                except FileNotFoundError:
                    pass
                except Exception:
                    self.log_event("resource", "upload.cleanup_failed", level="ERROR", upload_id=upload_id)
                    continue
                completed.append(upload_id)
            if completed:
                session = self.session_factory()
                try:
                    await maybe_await(session.execute(delete(UploadEntry).where(pending, UploadEntry.id.in_(completed))))
                    await maybe_await(session.commit())
                finally:
                    await maybe_await(session.close())

    def _request_upload_cleanup(self) -> None:
        if self._upload_cleanup_wakeup is not None:
            self._upload_cleanup_wakeup.set()

    async def _run_hooks(self, adapter: MapperAdapter, phase: str, ctx: OperationContext) -> None:
        for hook in adapter.resource.hooks:
            callback = getattr(hook, phase)
            if callback is None:
                continue
            if phase.startswith("after_"):
                try:
                    await maybe_await(callback(ctx))
                except Exception:
                    self.log_event("resource", "resource.after_hook_failed", level="ERROR",
                                   resource=ctx.resource, hook=phase)
            else:
                await maybe_await(callback(ctx))

    async def read_event_record(self, event: AdminEvent, principal: Principal) -> dict[str, Any]:
        """Explicit, scoped read: an event grants no permission to retrieve data.

        The principal is the subscriber's identity, not the actor who triggered
        the event. Deleted records correctly return 404.
        """
        if not isinstance(principal, Principal):
            raise AdminError(401, "A verified subscriber principal is required", "unauthorized")
        resolved = await maybe_await(self.auth.resolve(principal))
        if resolved is None:
            raise AdminError(401, "Subscriber identity expired", "unauthorized")
        principal = resolved
        if not event.resource or event.record_id is None:
            raise AdminError(422, "Event has no record reference", "validation_error")
        await self._authorize(principal, event.resource, "show")
        session = self.session_factory()
        try:
            adapter = self._adapter(event.resource)
            record = await adapter.get(session, event.record_id, principal)
            await self._authorize(principal, event.resource, "show", record)
            return adapter.serialize(record, await self._allowed_fields(principal, event.resource, view="show", record=record))
        finally:
            await maybe_await(session.close())

    def add_resource(self, resource: Resource | type) -> Resource:
        if isinstance(resource, type):
            resource = Resource(resource)
        validate_navigation(resource.navigation)
        icon_metadata(resource.icon)
        if not resource._features_applied:
            for feature in resource.features:
                if not callable(getattr(feature, "apply", None)):
                    raise TypeError("Resource features must implement apply(resource)")
                feature.apply(resource)
            resource._features_applied = True
        if resource._uploads_enabled and self.storage is None:
            raise ValueError("UploadFeature requires Admin(storage=...)")
        for action in resource.actions:
            icon_metadata(action.icon)
        adapter = MapperAdapter(resource)
        if resource.access:
            thresholds = [resource.access.read, resource.access.select, resource.access.write,
                          resource.access.create, resource.access.edit, resource.access.delete]
            unknown = [x for x in thresholds if x is not None and x not in self.role_weights]
            if unknown:
                raise ValueError(f"Unknown role threshold(s): {unknown}")
        for virtual in resource.virtual_fields.values():
            for role in (virtual.read_role, virtual.write_role):
                if role is not None and role not in self.role_weights:
                    raise ValueError(f"Unknown virtual field role: {role}")
        for config in resource.fields.values():
            for threshold in (config.read_role, config.write_role):
                if threshold is not None and threshold not in self.role_weights:
                    raise ValueError(f"Unknown field role: {threshold}")
        if resource.name in self.resources:
            raise ValueError(f"Duplicate admin resource: {resource.name}")
        self.resources[resource.name] = adapter
        self.log_event("lifecycle", "resource.registered", resource=resource.name)
        return resource

    def add_page(self, page: Page) -> None:
        validate_navigation(page.navigation)
        icon_metadata(page.icon)
        if page.min_role and page.min_role not in self.role_weights:
            raise ValueError(f"Unknown page role: {page.min_role}")
        if re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]*", page.name) is None:
            raise ValueError("Page name must be a URL-safe slug")
        if page.name in self.pages or page.name in self.resources:
            raise ValueError("Duplicate admin page: " + page.name)
        self.pages[page.name] = page
        self.log_event("lifecycle", "page.registered", page=page.name)

    def add_group(self, group: NavigationGroup) -> None:
        validate_navigation(group.path)
        icon_metadata(group.icon)
        if group.path in self.groups:
            raise ValueError("Duplicate navigation group: " + group.path)
        self.groups[group.path] = group

    def add_bridge(self, bridge: Bridge) -> None:
        if bridge.name in self.bridges:
            raise ValueError("Duplicate bridge: " + bridge.name)
        if bridge.min_role is not None and bridge.min_role not in self.role_weights:
            raise ValueError(f"Unknown bridge role: {bridge.min_role}")
        self.bridges[bridge.name] = bridge
        self.log_event("lifecycle", "bridge.registered", bridge=bridge.name)

    def _role_ok(self, principal: Principal, minimum: str | None) -> bool:
        if minimum is None:
            return False
        needed = self.role_weights.get(minimum)
        if needed is None:
            return False
        return any(self.role_weights.get(role, float("-inf")) >= needed for role in principal.roles)

    async def _can(self, principal: Principal, name: str, action: str, record: Any = None) -> bool:
        adapter = self._adapter(name)
        resource = adapter.resource
        capability = {"create": "allow_create", "edit": "allow_edit",
                      "delete": "allow_delete", "show": "allow_show"}.get(action)
        if capability and not getattr(resource, capability):
            return False
        if resource.access is not None:
            threshold = resource.access.threshold(action)
            if not self._role_ok(principal, threshold):
                return False
            if (action in ("create", "edit", "delete") or action.startswith("action:")) and not self._role_ok(
                principal, resource.access.read
            ):
                return False
        if resource.operation_policy is not None and not await maybe_await(
            resource.operation_policy(principal, action, record)
        ):
            return False
        # For older auth callbacks, selecting an option uses the same authorization as listing.
        auth_action = "list" if action == "select" else action
        return bool(await maybe_await(self.auth.authorize(principal, name, auth_action, record)))

    async def _allowed_fields(self, principal: Principal, name: str, *, edit: bool = False,
                              view: str | None = None, record: Any = None) -> set[str]:
        adapter = self._adapter(name)
        allowed = set()
        for field_name in adapter.columns:
            if not adapter.visible(field_name) or (view and not adapter.view_visible(field_name, view)):
                continue
            field = adapter.resource.fields.get(field_name)
            role = field.write_role if edit and field else field.read_role if field else None
            if role is not None and not self._role_ok(principal, role):
                continue
            if edit and field is not None and field.read_role is not None and not self._role_ok(principal, field.read_role):
                continue
            if field is not None:
                condition = field.write_when if edit else field.read_when
                if condition is not None and record is not None and not await maybe_await(condition(principal, record)):
                    continue
                # Dynamic field predicates cannot be safely used in sorting/filtering:
                # a hidden row value would otherwise be inferable by a query oracle.
                if not edit and field.read_when is not None and view in ("filter", "search"):
                    continue
            if edit and not adapter.writable(field_name, create=view == "create"):
                continue
            override = adapter.view_config(field_name, view or ("edit" if edit else "show"))
            if edit and override and override.readonly is True:
                continue
            # A blocked target must not expose its FK or permit editing it.
            parent = next((prop for prop in adapter.relations.values()
                           if prop.direction.name == "MANYTOONE"
                           and any(adapter.columns[field_name] is c for c in prop.local_columns)), None)
            if parent is not None:
                target = adapter._related_resource(parent, self.resources)
                if target and not (await self._can(principal, target, "select") or
                                   (not edit and await self._can(principal, target, "list"))):
                    continue
            allowed.add(field_name)
        for field_name, virtual in adapter.resource.virtual_fields.items():
            if view == "filter":
                continue
            if edit and virtual.setter is None:
                continue
            if not edit and virtual.getter is None:
                continue
            role = virtual.write_role if edit else virtual.read_role
            if role is None or self._role_ok(principal, role):
                allowed.add(field_name)
        return allowed

    async def _verify_foreign_keys(self, session: Any, principal: Principal,
                                   adapter: MapperAdapter, payload: dict, *, record: Any = None) -> None:
        from .orm import convert_value
        for prop in adapter.relations.values():
            if prop.direction.name != "MANYTOONE":
                continue
            pairs = [(name, remote) for local, remote in prop.local_remote_pairs
                     for name, column in adapter.columns.items() if column is local and local in prop.local_columns]
            if not any(name in payload for name, _ in pairs):
                continue
            target_name = adapter._related_resource(prop, self.resources)
            if target_name is None or not await self._can(principal, target_name, "select"):
                raise AdminError(403, "Related resource cannot be selected", "forbidden")
            target = self._adapter(target_name)
            values = [convert_value(adapter.columns[name], payload[name]) if name in payload
                      else getattr(record, name, None) for name, _ in pairs]
            if all(value is None for value in values):
                continue
            if any(value is None for value in values):
                raise AdminError(422, "Supply all components of the related key", "validation_error")
            predicates = []
            for (_, remote), value in zip(pairs, values):
                remote_name = next((name for name, column in target.columns.items() if column is remote), None)
                if remote_name is None:
                    raise AdminError(409, "Related resource key is not mapped", "integrity_error")
                predicates.append(getattr(target.resource.model, remote_name) == value)
            stmt = await target._scope(select(target.resource.model).where(*predicates), principal)
            rows = (await maybe_await(session.execute(stmt.limit(2)))).scalars().all()
            if len(rows) != 1 or not await self._can(principal, target_name, "select", rows[0]):
                raise AdminError(409, "Related record is not selectable", "integrity_error")

    async def _create_record(
        self, session: Any, adapter: MapperAdapter, principal: Principal, payload: dict,
        *, members: list | None = None,
    ) -> JSONResponse:
        name = adapter.resource.name
        write_fields = await self._allowed_fields(principal, name, edit=True, view="create")
        rejected = set(payload) - write_fields
        if rejected:
            if all(field in adapter.columns and not adapter.writable(field, create=True) for field in rejected):
                raise AdminError(422, "Unknown or read-only fields", "validation_error",
                                 {"fields": sorted(rejected)})
            raise AdminError(403, "Cannot write one or more fields", "forbidden")
        ctx = OperationContext("create", name, principal, session, payload=payload.copy())
        await self._run_hooks(adapter, "before_create", ctx)
        ctx.payload = validate_payload(adapter.resource.create_schema, ctx.payload)
        if set(ctx.payload) - write_fields:
            raise AdminError(403, "Hook supplied unauthorized fields", "forbidden")
        await self._verify_foreign_keys(session, principal, adapter, ctx.payload)
        record = await adapter._stage_create(session, ctx.payload, principal, context=ctx)
        if members is not None:
            members.append(record)
        await adapter._flush_create(session, record, ctx.payload, principal)
        await maybe_await(session.refresh(record))
        identifier = adapter.record_identifier(record)
        record_id = identifier if adapter.composite else getattr(record, adapter.pk_name)
        if adapter.resource.create_handler is not None:
            await self._verify_foreign_keys(session, principal, adapter,
                {field: getattr(record, field) for field in adapter.foreign_key_fields})
        if adapter.resource.scope is not None:
            await adapter.get(session, identifier, principal)
        if members is not None:
            await self._authorize(principal, name, "select", record)
        fields = await self._allowed_fields(principal, name, view="show", record=record)
        response = JSONResponse({"record": adapter.serialize(record, fields)}, status_code=201)
        await adapter._commit(session)
        ctx.record = record
        await self._after_write(adapter, "after_create", ctx)
        self.log_event("resource", "resource.created", principal=principal, resource=name, record_id=record_id)
        await self._publish(ResourceCreated(
            resource=name, record_id=identifier, actor_id=str(principal.id),
            fields=field_refs(adapter, payload), **event_context(),
        ))
        return response

    async def _after_write(self, adapter: MapperAdapter, phase: str, ctx: OperationContext) -> None:
        if not any(getattr(hook, phase) is not None for hook in adapter.resource.hooks):
            return
        try:
            if sa_inspect(ctx.record).expired:
                await maybe_await(ctx.session.refresh(ctx.record))
        except SQLAlchemyError:
            self.log_event("resource", "resource.after_hook_refresh_failed", level="ERROR", resource=ctx.resource)
        else:
            await self._run_hooks(adapter, phase, ctx)

    async def _visible_actions(self, principal: Principal, name: str, record: Any) -> list[str]:
        adapter = self._adapter(name)
        visible = []
        for action in adapter.resource.actions:
            if action.kind != "record":
                continue
            if not await self._can(principal, name, "action:" + action.name, record):
                continue
            predicate = action.visible
            allowed = (await maybe_await(predicate(principal, record))) if callable(predicate) else predicate
            if allowed:
                visible.append(action.name)
        return visible

    def _adapter(self, name: str) -> MapperAdapter:
        adapter = self.resources.get(name)
        if adapter is None:
            raise AdminError(404, "Resource not found", "not_found")
        return adapter

    async def _session_identity(self, session_id: object) -> tuple[Principal, SessionIdentity]:
        if not isinstance(session_id, str):
            raise AdminError(401, "Sign in required", "unauthorized")
        identity = await self.session_store.get(session_id)
        if (identity is None or identity.audience != self._session_audience
                or identity.expires_at <= time.time()):
            raise AdminError(401, "Session expired", "unauthorized")
        resolved = await maybe_await(self.auth.resolve(deepcopy(identity.principal)))
        if resolved is None or resolved.id != identity.principal.id:
            await self.session_store.revoke(session_id)
            raise AdminError(401, "Session expired", "unauthorized")
        return resolved, identity

    async def _principal(self, request: Request) -> Principal:
        try:
            principal, identity = await self._session_identity(request.session.get("sid"))
        except AdminError as error:
            if error.status == 401:
                request.session.clear()
            raise
        request.state.pyntral_csrf = identity.csrf
        return principal

    async def _end_session(self, request: Request) -> None:
        session_id = request.session.get("sid")
        if isinstance(session_id, str):
            identity = await self.session_store.get(session_id)
            if identity is not None and identity.audience == self._session_audience:
                await self.session_store.revoke(session_id)
        request.session.clear()

    async def _start_session(self, request: Request, principal: Principal) -> dict:
        await self._end_session(request)
        session_id = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        await self.session_store.put(session_id, SessionIdentity(
            deepcopy(principal), csrf, self._session_audience, time.time() + self.session_max_age,
        ))
        request.session["sid"] = session_id
        return {"user": principal.as_dict(), "csrf": csrf}

    @staticmethod
    def _require_version(adapter: MapperAdapter, record: Any, request: Request) -> None:
        field_name = adapter.resource.version_field
        if field_name is None:
            return
        supplied = request.headers.get("If-Match")
        if supplied is None:
            raise AdminError(428, "Record version required (If-Match)", "precondition_required")
        expected = str(getattr(record, field_name))
        if supplied.strip('"') != expected:
            raise AdminError(412, "Record changed since it was loaded", "precondition_failed")

    def _csrf(self, request: Request) -> None:
        token = getattr(request.state, "pyntral_csrf", None)
        supplied = request.headers.get("X-CSRF-Token", "")
        if not isinstance(token, str) or not hmac.compare_digest(token.encode(), supplied.encode()):
            raise AdminError(403, "Invalid CSRF token", "csrf_error")

    async def _authorize(
        self, principal: Principal, name: str, action: str, record: Any = None
    ) -> None:
        if not await self._can(principal, name, action, record):
            raise AdminError(403, "Permission denied", "forbidden")

    def _dist(self) -> Path:
        if self.dist_dir:
            return self.dist_dir
        configured = os.environ.get("PYNTRAL_DIST")
        if configured:
            return Path(configured).resolve()
        local = (Path.cwd() / ".pyntral" / "dist").resolve()
        if (local / "index.html").is_file():
            return local
        return (Path(__file__).parent / "web_dist").resolve()

    def _register_routes(self) -> None:
        api = self.api

        @api.middleware("http")
        async def security_headers(request: Request, call_next):
            started = time.perf_counter()
            request_id = uuid.uuid4().hex
            token = request_id_var.set(request_id)
            try:
                try:
                    response = await call_next(request)
                except Exception:
                    self.log_event("http", "http.unhandled_exception", level="ERROR",
                                   method=request.method)
                    raise
                response.headers["X-Content-Type-Options"] = "nosniff"
                response.headers["X-Frame-Options"] = "DENY"
                response.headers["Referrer-Policy"] = "same-origin"
                response.headers["X-Request-ID"] = request_id
                path = request.scope.get("path", "")
                root = request.scope.get("root_path", "").rstrip("/")
                if root and path.startswith(root + "/"):
                    path = path[len(root):]
                if path.startswith(("/api/", "/auth/")):
                    response.headers["Cache-Control"] = "no-store"
                duration_ms = round((time.perf_counter() - started) * 1000, 2)
                mode = self.logging_config.http
                status = response.status_code
                slow = duration_ms >= self.logging_config.slow_request_ms
                should_log = (mode == "all" or
                              mode == "errors" and status >= 400 or
                              mode == "slow" and slow)
                if should_log:
                    # Never log URL query strings or untrusted route parameters.
                    route = request.scope.get("route")
                    template = getattr(route, "path", "<unmatched>")
                    level = "ERROR" if status >= 500 else "WARNING" if status >= 400 else "INFO"
                    self.log_event("http", "http.request", level=level,
                                   method=request.method, route=template,
                                   status=status, duration_ms=duration_ms)
                return response
            finally:
                request_id_var.reset(token)

        @api.exception_handler(AdminError)
        async def admin_error(_request: Request, error: AdminError) -> JSONResponse:
            if error.status in (401, 403):
                self.log_event("security", "security.access_denied", level="WARNING",
                               status=error.status, code=error.code)
            return JSONResponse(
                status_code=error.status,
                content={"error": {"code": error.code, "message": error.message,
                                   "details": error.details}},
            )

        @api.get("/auth/config")
        async def login_config() -> dict:
            # Explicit public presentation contract. Do not expose resource metadata,
            # bridges, principals, credentials or per-principal resolver output here.
            return {"login": self.login_config.metadata(self.title, self.sidebar.header),
                    "theme": {"default": self.default_theme, "animations": self.animations,
                              "tokens": {mode: dict(self.theme.get(mode, {})) for mode in ("light", "dark")}},
                    "localization": {"code": self.default_locale,
                                     "messages": {k: v for k, v in self.translations.get(self.default_locale, {}).items()
                                                  if k.startswith("login.")}}}

        @api.get("/auth/me")
        async def me(request: Request) -> dict:
            try:
                principal = await self._principal(request)
            except AdminError:
                return {"user": None, "csrf": None}
            return {"user": principal.as_dict(), "csrf": request.state.pyntral_csrf}

        @api.post("/auth/login")
        async def login(request: Request) -> dict:
            # Reject cross-origin browser form submission (login CSRF).
            origin = request.headers.get("origin")
            if origin:
                parsed = urlparse(origin)
                if parsed.netloc != request.url.netloc or parsed.scheme != request.url.scheme:
                    raise AdminError(403, "Cross-origin login rejected", "forbidden")
            payload = await self._body(request)
            username, password = payload.get("username"), payload.get("password")
            if not isinstance(username, str) or not isinstance(password, str) or len(username) > 320 or len(password) > 4096:
                raise AdminError(422, "Invalid credentials format", "validation_error")
            user = await maybe_await(self.auth.login(username, password))
            if not isinstance(user, Principal):
                self.log_event("auth", "auth.login_failed", level="WARNING")
                await self._publish(LoginFailed(**event_context()))
                raise AdminError(401, "Invalid username or password", "invalid_credentials")
            state = await self._start_session(request, user)
            self.log_event("auth", "auth.login_success", principal=user)
            await self._publish(LoginSucceeded(actor_id=str(user.id), **event_context()))
            return state

        @api.post("/auth/external")
        async def external_login(request: Request) -> dict:
            """Exchange an externally verified bearer for the regular admin session.

            The configured AuthBackend.login_token MUST verify signature, issuer,
            audience, expiry and other provider claims; this route does not trust
            client-supplied user IDs or roles.
            """
            origin = request.headers.get("origin")
            if origin:
                parsed = urlparse(origin)
                if parsed.netloc != request.url.netloc or parsed.scheme != request.url.scheme:
                    raise AdminError(403, "Cross-origin login rejected", "forbidden")
            payload = await self._body(request)
            token = payload.get("token")
            if not isinstance(token, str) or not 1 <= len(token) <= 16384:
                raise AdminError(422, "Invalid external token", "validation_error")
            user = await maybe_await(self.auth.login_token(token))
            if not isinstance(user, Principal):
                self.log_event("auth", "auth.external_login_failed", level="WARNING")
                await self._publish(LoginFailed(**event_context()))
                raise AdminError(401, "External authentication failed", "invalid_credentials")
            state = await self._start_session(request, user)
            self.log_event("auth", "auth.login_success", principal=user)
            await self._publish(LoginSucceeded(actor_id=str(user.id), **event_context()))
            return state

        @api.post("/auth/logout")
        async def logout(request: Request, _principal: Principal = Depends(self._principal)) -> dict:
            self._csrf(request)
            await self._end_session(request)
            self.log_event("auth", "auth.logout", principal=_principal)
            await self._publish(LogoutSucceeded(actor_id=str(_principal.id), **event_context()))
            return {"ok": True}

        @api.get("/api/realtime", include_in_schema=False)
        async def realtime_feed(
            request: Request, _principal: Principal = Depends(self._principal),
        ):
            if self.realtime is None:
                raise AdminError(404, "Realtime updates are disabled", "not_found")
            try:
                queue, unsubscribe = self.realtime.listen()
            except RuntimeError as exc:
                raise AdminError(429, "Too many realtime subscribers", "rate_limited") from exc

            session_id = request.session.get("sid")

            async def stream():
                deadline = time.monotonic() + 300
                try:
                    yield ": connected\n\n"
                    while not await request.is_disconnected():
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            return
                        try:
                            await asyncio.wait_for(queue.get(), timeout=min(20.0, remaining))
                        except TimeoutError:
                            message = ": ping\n\n"
                        else:
                            message = "event: invalidate\ndata: {}\n\n"
                        if time.monotonic() >= deadline:
                            return
                        try:
                            await self._session_identity(session_id)
                        except AdminError:
                            return
                        yield message
                finally:
                    unsubscribe()

            return StreamingResponse(stream(), media_type="text/event-stream",
                                     headers={"Cache-Control": "no-store",
                                              "X-Accel-Buffering": "no"})

        @api.get("/api/schema")
        async def schema(principal: Principal = Depends(self._principal)) -> dict:
            resources = []
            can_read = {name: await self._can(principal, name, "list") for name in self.resources}
            can_select = {name: await self._can(principal, name, "select") for name in self.resources}
            for name, adapter in self.resources.items():
                permitted = can_read[name]
                locked = not permitted and bool(adapter.resource.access and
                    adapter.resource.access.navigation == "lock")
                if not permitted and not can_select[name] and not locked:
                    continue
                metadata = adapter.metadata(self.resources)
                metadata["navigationState"] = "enabled" if permitted else (
                    "locked" if locked else "hidden")
                metadata["capabilities"] = {
                    "list": permitted,
                    "select": can_select[name],
                    "show": permitted and await self._can(principal, name, "show"),
                    "create": permitted and await self._can(principal, name, "create"),
                    "edit": permitted and await self._can(principal, name, "edit"),
                    "delete": permitted and await self._can(principal, name, "delete"),
                }
                if not permitted:
                    metadata.update(fields=[], listFields=[], searchFields=[], relationships=[], actions=[], jobs=[], crudSlots={})
                else:
                    read_fields = await self._allowed_fields(principal, name)
                    edit_fields = await self._allowed_fields(principal, name, edit=True, view="edit")
                    create_fields = await self._allowed_fields(principal, name, edit=True, view="create")
                    # Write-only virtual fields must remain in create/edit forms,
                    # but never become readable list/show fields or filter targets.
                    # Read and write permissions are independent here.
                    metadata["fields"] = [f for f in metadata["fields"]
                                          if f["name"] in read_fields or f["name"] in edit_fields or f["name"] in create_fields]
                    for field in metadata["fields"]:
                        field["readonly"] = (field["readonly"] or
                            not (metadata["capabilities"]["edit"] or metadata["capabilities"]["create"])
                            or field["name"] not in (edit_fields | create_fields))
                        if field["relation"] and not can_select.get(field["relation"]["resource"], False):
                            field["relation"] = None
                    for field in metadata["fields"]:
                        for view, option in field["views"].items():
                            allowed = (field["name"] in create_fields if view == "create" else
                                       field["name"] in edit_fields if view == "edit" else field["name"] in read_fields)
                            option["visible"] = option["visible"] and allowed
                            if view in ("create", "edit"):
                                option["readonly"] = option["readonly"] or not metadata["capabilities"][view] or not allowed
                    metadata["listFields"] = [n for n in metadata["listFields"] if n in read_fields]
                    metadata["searchFields"] = [n for n in metadata["searchFields"] if n in read_fields
                        and (n not in adapter.resource.fields or adapter.resource.fields[n].read_when is None)]
                    for field in metadata["fields"]:
                        if field["name"] in adapter.resource.fields and adapter.resource.fields[field["name"]].read_when is not None:
                            field["filterOperators"] = []
                            field["sortable"] = False
                            field["views"]["filter"]["visible"] = False
                    metadata["relationships"] = [r for r in metadata["relationships"]
                        if can_read.get(r["resource"], False)]
                    for relation in metadata["relationships"]:
                        if "editable" in relation:
                            relation["editable"] = (metadata["capabilities"]["edit"]
                                and can_select.get(relation["resource"], False))
                    metadata["actions"] = [a for a in metadata["actions"]
                        if await self._can(principal, name, "action:" + a["name"])]
                    metadata["jobs"] = [a for a in metadata["jobs"] if self.enable_jobs
                        and await self._can(principal, name, "action:" + a["name"])]
                resources.append(metadata)
            visible_paths = [r["navigation"] for r in resources
                             if r["navigation"] and r["navigationState"] != "hidden"]
            pages = [{"name": p.name, "label": p.label, "component": p.component,
                      "icon": icon_metadata(p.icon), "navigation": p.navigation, "navigationOrder": p.navigation_order}
                     for p in self.pages.values()
                     if (p.min_role is None or self._role_ok(principal, p.min_role))
                     and await maybe_await(self.auth.authorize(principal, "page:" + p.name, "view"))]
            visible_paths.extend(p["navigation"] for p in pages if p["navigation"])
            locale = self.default_locale
            if self.locale_resolver is not None:
                resolved = await maybe_await(self.locale_resolver(principal))
                if isinstance(resolved, str) and re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", resolved):
                    locale = resolved
            # Literal labels stay untouched. Explicit @keys resolve against the
            # selected locale with an English fallback, without translating IDs.
            def localized(value: Any) -> Any:
                if not isinstance(value, str) or re.fullmatch(r"@[a-zA-Z][a-zA-Z0-9_.-]*", value) is None:
                    return value
                key = value[1:]
                return (self.translations.get(locale, {}).get(key)
                        or self.translations.get("en", {}).get(key)
                        or key)

            for metadata in resources:
                metadata["label"] = localized(metadata["label"])
                for field_data in metadata.get("fields", []):
                    field_data["label"] = localized(field_data.get("label"))
                    field_data["help"] = localized(field_data.get("help"))
                for operation in ("actions", "jobs"):
                    for action_data in metadata.get(operation, []):
                        for attribute in ("label", "confirmation"):
                            if attribute in action_data:
                                action_data[attribute] = localized(action_data[attribute])
                for mode in ("form", "detail"):
                    for section in metadata.get("layouts", {}).get(mode, []):
                        section["title"] = localized(section["title"])
                for relationship in metadata.get("relationships", []):
                    relationship["label"] = localized(relationship.get("label"))
            for page in pages:
                page["label"] = localized(page["label"])
            theme_default = self.default_theme
            theme_tokens = {mode: dict(self.theme.get(mode, {})) for mode in ("light", "dark")}
            if self.theme_resolver is not None:
                # The principal is server-verified; never accept theme overrides
                # supplied by the browser as authorization or trusted metadata.
                preferences = await maybe_await(self.theme_resolver(principal))
                if not isinstance(preferences, dict):
                    raise ValueError("theme_resolver must return a dictionary")
                preferred = preferences.get("default")
                if preferred is not None:
                    if preferred not in ("system", "light", "dark"):
                        raise ValueError("theme_resolver.default must be system, light or dark")
                    theme_default = preferred
                overrides = preferences.get("tokens", {})
                if not isinstance(overrides, dict) or set(overrides) - {"light", "dark"}:
                    raise ValueError("theme_resolver.tokens must contain light/dark mappings")
                for mode, tokens in overrides.items():
                    if not isinstance(tokens, dict) or any(
                        not isinstance(k, str) or re.fullmatch(r"[a-z][a-z0-9-]{0,63}", k) is None
                        or not isinstance(v, str) or len(v) > 256 for k, v in tokens.items()
                    ):
                        raise ValueError("Invalid theme token override")
                    theme_tokens[mode].update(tokens)
            return {"title": self.title, "realtime": self.realtime is not None,
                    "resources": resources,
                    "localization": {"code": locale, "messages": self.translations.get(locale, {})},
                    "navigation": {"groups": [
                        {"path": g.path, "icon": icon_metadata(g.icon), "order": g.order}
                        for g in self.groups.values() if any(
                            path == g.path or path.startswith(g.path + "/") for path in visible_paths
                        )], "showDashboard": self.show_dashboard, "sidebar": self.sidebar.metadata(self.title)},
                    "theme": {"default": theme_default,
                              "animations": self.animations,
                              "tokens": theme_tokens},
                    "bridges": [b.metadata() for b in self.bridges.values()
                                if (b.min_role is None or self._role_ok(principal, b.min_role))
                                and await maybe_await(self.auth.authorize(principal, "bridge:" + b.name, "invoke"))],
                    "pages": pages}

        @api.post("/api/bridge/{name}")
        async def invoke_bridge(
            name: str, request: Request, principal: Principal = Depends(self._principal)
        ) -> dict:
            self._csrf(request)
            bridge = self.bridges.get(name)
            if bridge is None:
                raise AdminError(404, "Bridge not found", "not_found")
            if (bridge.min_role is not None and not self._role_ok(principal, bridge.min_role)) or not await maybe_await(self.auth.authorize(principal, "bridge:" + name, "invoke")):
                raise AdminError(403, "Permission denied", "forbidden")
            uploaded = None
            if bridge.upload is None:
                payload = await self._body(request)
            else:
                raw_input = request.headers.get("X-Pyntral-Input", "%7B%7D")
                if len(raw_input) > 8192:
                    raise AdminError(413, "Bridge upload metadata too large", "request_too_large")
                try:
                    payload = json.loads(unquote(raw_input, errors="strict"))
                    if not isinstance(payload, dict):
                        raise ValueError("Expected JSON object")
                except (ValueError, UnicodeError, RecursionError):
                    raise AdminError(422, "Invalid bridge upload metadata", "validation_error") from None
                if not request.headers.get("X-Filename"):
                    raise AdminError(422, "Expected a file upload", "validation_error")
                filename = safe_upload_name(unquote(request.headers["X-Filename"]))
                try:
                    mime = normalize_mime(request.headers.get("Content-Type", ""), filename)
                except ValueError:
                    raise AdminError(422, "Invalid content type", "validation_error") from None
                if not bridge.upload.accepts(mime):
                    raise AdminError(415, "Unsupported upload content type", "unsupported_media_type")
            try:
                parsed = bridge.input_model.model_validate(payload)
            except ValidationError as exc:
                raise AdminError(422, "Invalid bridge input", "validation_error", exc.errors(
                    include_url=False, include_context=False, include_input=False)) from None
            if bridge.upload is not None:
                content = bytearray()
                async for chunk in request.stream():
                    if len(content) + len(chunk) > bridge.upload.max_bytes:
                        raise AdminError(413, "Bridge upload too large", "upload_too_large")
                    content.extend(chunk)
                if not content:
                    raise AdminError(422, "Upload must not be empty", "validation_error")
                uploaded = BridgeFile(filename, mime, bytes(content))
            session = self.session_factory()
            try:
                output = await maybe_await(bridge.handler(parsed, BridgeContext(principal, session, uploaded)))
                try:
                    validated = bridge.output_model.model_validate(output)
                except ValidationError as exc:
                    # Implementation error; do not leak arbitrary output content to clients.
                    raise AdminError(500, "Bridge output did not match its model", "bridge_output_error") from exc
                self.log_event("bridge", "bridge.invoked", principal=principal, bridge=name)
                return {"result": validated.model_dump(mode="json")}
            finally:
                await maybe_await(session.close())

        async def _upload_owner(name: str, identifier: str, principal: Principal,
                                session: Any, *, edit: bool = False,
                                lock: bool | None = None) -> tuple[MapperAdapter, Any]:
            adapter = self._adapter(name)
            if not adapter.resource._uploads_enabled or self.storage is None:
                raise AdminError(404, "Uploads not enabled for this resource", "not_found")
            await self._authorize(principal, name, "edit" if edit else "show")
            record = await adapter.get(session, identifier, principal, lock=lock)
            await self._authorize(principal, name, "edit" if edit else "show", record)
            return adapter, record

        @api.get("/api/resources/{name}/{identifier}/uploads")
        async def list_uploads(name: str, identifier: str,
                               principal: Principal = Depends(self._principal)) -> dict:
            session = self.session_factory()
            try:
                await self._begin_upload_transaction(session, write=False)
                adapter, record = await _upload_owner(name, identifier, principal, session, lock=False)
                record_id = adapter.persisted_identifier(record, 120)
                rows = (await maybe_await(session.execute(select(UploadEntry).where(
                    UploadEntry.resource == name, UploadEntry.record_id == record_id
                ).order_by(UploadEntry.id).limit(100)))).scalars().all()
                return {"items": [{"id": row.id, "filename": row.filename,
                                   "content_type": row.content_type, "size_bytes": row.size_bytes}
                                  for row in rows]}
            finally:
                await maybe_await(session.close())

        @api.post("/api/resources/{name}/{identifier}/uploads", status_code=201)
        async def upload_resource_file(name: str, identifier: str, request: Request,
                                       principal: Principal = Depends(self._principal)) -> dict:
            self._csrf(request)
            session = self.session_factory()
            try:
                adapter, _ = await _upload_owner(name, identifier, principal, session, edit=True)
                await maybe_await(session.rollback())
                from urllib.parse import unquote
                filename = safe_upload_name(unquote(request.headers.get("X-Filename", "attachment")))
                try:
                    mime = normalize_mime(request.headers.get("Content-Type", ""), filename)
                except ValueError:
                    raise AdminError(422, "Invalid content type", "validation_error") from None
                content = bytearray()
                async for chunk in request.stream():
                    if len(content) + len(chunk) > adapter.resource._upload_max_bytes:
                        raise AdminError(413, "Upload exceeds configured size limit", "upload_too_large")
                    content.extend(chunk)
                if not content:
                    raise AdminError(422, "Upload must not be empty", "validation_error")
                key = uuid.uuid4().hex
                upload_id = str(uuid.uuid4())
                try:
                    await self.storage.put(key, bytes(content), mime)
                    await self._begin_upload_transaction(session, write=True)
                    _, record = await _upload_owner(name, identifier, principal, session, edit=True, lock=True)
                    record_id = adapter.persisted_identifier(record, 120)
                    session.add(UploadEntry(
                        id=upload_id, resource=name, record_id=record_id, object_key=key,
                        filename=filename, content_type=mime, size_bytes=len(content),
                    ))
                    await adapter._commit(session)
                except Exception:
                    await maybe_await(session.rollback())
                    try:
                        await self.storage.delete(key)
                    except Exception:
                        self.log_event("resource", "upload.compensation_failed", level="ERROR", upload_id=upload_id)
                    raise
                return {"id": upload_id, "filename": filename, "size_bytes": len(content)}
            finally:
                await maybe_await(session.close())

        async def _get_upload(upload_id: str, principal: Principal, session: Any,
                              *, edit: bool = False) -> UploadEntry:
            await self._begin_upload_transaction(session, write=edit)
            entry = await maybe_await(session.get(UploadEntry, upload_id))
            if entry is None or entry.record_id == _PENDING_DELETE_RECORD:
                raise AdminError(404, "Upload not found", "not_found")
            adapter, owner = await _upload_owner(entry.resource, entry.record_id, principal, session,
                                                  edit=edit, lock=edit)
            # A resource could have been deleted while waiting on its row lock.
            # Reload the entry while holding the lock and reject legacy noncanonical links.
            live = (await maybe_await(session.execute(select(UploadEntry).where(
                UploadEntry.id == upload_id, UploadEntry.resource == adapter.resource.name,
                UploadEntry.record_id == adapter.persisted_identifier(owner, 120),
            )))).scalar_one_or_none()
            if live is None:
                raise AdminError(404, "Upload not found", "not_found")
            return live

        @api.get("/api/uploads/{upload_id}")
        async def download_resource_file(upload_id: str,
                                         principal: Principal = Depends(self._principal)) -> Response:
            session = self.session_factory()
            try:
                entry = await _get_upload(upload_id, principal, session)
                key, filename = entry.object_key, entry.filename
            finally:
                await maybe_await(session.close())
            try:
                content = await self.storage.get(key)
            except FileNotFoundError:
                raise AdminError(404, "Stored object missing", "not_found") from None
            from urllib.parse import quote
            return Response(content, media_type="application/octet-stream", headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}",
                "Content-Security-Policy": "default-src 'none'",
            })

        @api.delete("/api/uploads/{upload_id}")
        async def delete_resource_file(upload_id: str, request: Request,
                                       principal: Principal = Depends(self._principal)) -> dict:
            self._csrf(request)
            session = self.session_factory()
            try:
                entry = await _get_upload(upload_id, principal, session, edit=True)
                adapter = self._adapter(entry.resource)
                entry.record_id = _PENDING_DELETE_RECORD
                await adapter._commit(session)
                self._request_upload_cleanup()
                return {"ok": True}
            finally:
                await maybe_await(session.close())

        @api.get("/api/resources/{name}/options")
        async def options(name: str, q: str = "", ids: str = "", principal: Principal = Depends(self._principal)) -> dict:
            await self._authorize(principal, name, "select")
            session = self.session_factory()
            try:
                async def fields_for_option(row: Any) -> set[str] | None:
                    if not await self._can(principal, name, "select", row):
                        return None
                    return await self._allowed_fields(principal, name, record=row)

                return {"items": await self._adapter(name).options(
                    session, principal, q, ids=ids.split(",") if ids else None,
                    allowed_fields=await self._allowed_fields(principal, name),
                    per_record_fields=fields_for_option,
                )}
            finally:
                await maybe_await(session.close())

        @api.get("/api/resources/{name}")
        async def list_records(name: str, request: Request, principal: Principal = Depends(self._principal)) -> dict:
            await self._authorize(principal, name, "list")
            params = request.query_params
            try:
                offset = int(params.get("offset", "0"))
                limit = int(params.get("limit", "20"))
            except ValueError:
                raise AdminError(422, "Invalid pagination", "validation_error") from None
            if len([key for key in params.keys() if key.startswith("filter.")]) > 80:
                raise AdminError(422, "Too many filters", "invalid_filter")
            if any(len(params.getlist(k)) > 1 for k in params.keys() if k.startswith("filter.")):
                raise AdminError(422, "Duplicate filter query parameter", "invalid_filter")
            filters = {k.removeprefix("filter."): v for k, v in params.items() if k.startswith("filter.")}
            session = self.session_factory()
            try:
                adapter = self._adapter(name)
                read_fields = await self._allowed_fields(principal, name, view="list")
                filter_fields = await self._allowed_fields(principal, name, view="filter")
                async def fields_for_row(row):
                    return await self._allowed_fields(principal, name, view="list", record=row)
                result = await adapter.list(
                    session, principal, offset=offset, limit=limit, q=params.get("q", ""),
                    sort=params.get("sort"), desc=params.get("desc") == "true", filters=filters,
                    allowed_fields=read_fields, filter_fields=filter_fields,
                    per_record_fields=fields_for_row,
                )
                if adapter.resource.actions:
                    # Evaluated against the actual scoped ORM records; no frontend-only ACL.
                    result["actionsByRecord"] = {}
                    ids = [str(item[adapter.identity_field]) for item in result["items"] if adapter.identity_field in item]
                    if ids:
                        stmt = await adapter._scope(select(adapter.resource.model).where(
                            adapter.identities_predicate(ids)), principal)
                        records = (await maybe_await(session.execute(stmt))).scalars().all()
                        for record in records:
                            result["actionsByRecord"][adapter.record_identifier(record)] = (
                                await self._visible_actions(principal, name, record)
                            )
                return result
            finally:
                await maybe_await(session.close())

        @api.get("/api/resources/{name}/export")
        async def export_records(
            name: str, request: Request, principal: Principal = Depends(self._principal),
        ) -> Response:
            """Export a bounded, authorized snapshot of the current resource query."""
            await self._authorize(principal, name, "list")
            params = request.query_params
            fmt = params.get("format", "csv")
            if fmt not in ("csv", "json"):
                raise AdminError(422, "Export format must be csv or json", "validation_error")
            try:
                offset = int(params.get("offset", "0"))
                limit = int(params.get("limit", "1000"))
            except ValueError:
                raise AdminError(422, "Invalid export range", "validation_error") from None
            if offset < 0 or not 1 <= limit <= 10000:
                raise AdminError(422, "Export offset must be nonnegative and limit 1..10000", "validation_error")
            if len([key for key in params.keys() if key.startswith("filter.")]) > 80:
                raise AdminError(422, "Too many filters", "invalid_filter")
            if any(len(params.getlist(key)) > 1 for key in params.keys() if
                   key.startswith("filter.") or key == "columns"):
                raise AdminError(422, "Duplicate export parameter", "validation_error")
            adapter = self._adapter(name)
            read_fields = await self._allowed_fields(principal, name, view="list")
            filter_fields = await self._allowed_fields(principal, name, view="filter")
            available = [field for field in adapter.metadata(self.resources)["listFields"]
                         if field in read_fields]
            requested = params.get("columns")
            columns = requested.split(",") if requested is not None else available
            if (not columns or len(columns) > 100 or len(set(columns)) != len(columns)
                    or any(column not in available for column in columns)):
                raise AdminError(422, "Invalid or unauthorized export columns", "validation_error")
            filters = {key.removeprefix("filter."): value for key, value in params.items()
                       if key.startswith("filter.")}
            session = self.session_factory()
            try:
                async def fields_for_row(row: Any) -> set[str]:
                    return await self._allowed_fields(principal, name, view="list", record=row)

                rows: list[dict[str, Any]] = []
                while len(rows) < limit:
                    batch = await adapter.list(
                        session, principal, offset=offset + len(rows),
                        limit=min(200, limit - len(rows)), q=params.get("q", ""),
                        sort=params.get("sort"), desc=params.get("desc") == "true",
                        filters=filters, allowed_fields=read_fields, filter_fields=filter_fields,
                        per_record_fields=fields_for_row,
                    )
                    if not batch["items"]:
                        break
                    rows.extend(batch["items"])
                    if offset + len(rows) >= batch["total"]:
                        break
            finally:
                await maybe_await(session.close())

            exported = [{field: row.get(field) for field in columns} for row in rows]
            if fmt == "json":
                body = json.dumps(exported, ensure_ascii=False, default=str)
                media_type = "application/json"
            else:
                stream = io.StringIO(newline="")
                writer = csv.writer(stream)
                writer.writerow(columns)
                for row in exported:
                    cells = []
                    for column in columns:
                        value = row[column]
                        if isinstance(value, (dict, list)):
                            value = json.dumps(value, ensure_ascii=False, default=str)
                        elif value is None:
                            value = ""
                        else:
                            value = str(value)
                        # Spreadsheet apps interpret untrusted leading =,+,-,@ as formulae.
                        if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
                            value = "'" + value
                        cells.append(value)
                    writer.writerow(cells)
                body = "\ufeff" + stream.getvalue()
                media_type = "text/csv"
            return Response(
                body, media_type=media_type,
                headers={
                    "Content-Disposition": f'attachment; filename="{name}.{fmt}"',
                    "Cache-Control": "private, no-store",
                    "X-Export-Rows": str(len(rows)),
                },
            )

        @api.post("/api/resources/{name}", status_code=201)
        async def create(name: str, request: Request, principal: Principal = Depends(self._principal)) -> Response:
            self._csrf(request)
            await self._authorize(principal, name, "create")
            payload = await self._body(request)
            adapter = self._adapter(name)
            session = self.session_factory()
            try:
                return await self._create_record(session, adapter, principal, payload)
            finally:
                await maybe_await(session.close())

        @api.post("/api/resources/{name}/jobs/{job_name}", status_code=202)
        async def start_resource_job(
            name: str, job_name: str, request: Request,
            principal: Principal = Depends(self._principal),
        ) -> dict:
            self._csrf(request)
            adapter = self._adapter(name)
            job = next((item for item in adapter.resource.jobs if item.name == job_name), None) if self.enable_jobs else None
            if job is None:
                raise AdminError(404, "Job action not found", "not_found")
            await self._authorize(principal, name, "action:" + job_name)
            payload = await self._body(request, max_bytes=8192)
            try:
                record = self.jobs.submit(job, resource=name, principal=principal,
                                          payload=payload, session_factory=self.session_factory)
            except RuntimeError as exc:
                raise AdminError(429, "Too many background jobs", "rate_limited") from exc
            self.log_event("action", "job.started", resource=name, action=job_name,
                           principal=principal)
            return {"job": record.public()}

        @api.get("/api/jobs/{job_id}")
        async def get_resource_job(
            job_id: str, principal: Principal = Depends(self._principal),
        ) -> dict:
            record = self.jobs.get(job_id, owner_id=str(principal.id))
            if record is None:
                raise AdminError(404, "Job not found", "not_found")
            return {"job": record.public()}

        @api.delete("/api/jobs/{job_id}")
        async def cancel_resource_job(
            job_id: str, request: Request,
            principal: Principal = Depends(self._principal),
        ) -> dict:
            self._csrf(request)
            record = self.jobs.get(job_id, owner_id=str(principal.id))
            if record is None:
                raise AdminError(404, "Job not found", "not_found")
            if not record.cancellable:
                raise AdminError(403, "Job cancellation is disabled", "forbidden")
            self.jobs.cancel(job_id, owner_id=str(principal.id))
            return {"job": record.public()}

        @api.post("/api/resources/{name}/actions/{action_name}")
        async def run_collection_action(
            name: str, action_name: str, request: Request,
            principal: Principal = Depends(self._principal),
        ) -> dict:
            """Explicit resource/bulk action route: no implicit SQL mass updates."""
            self._csrf(request)
            adapter = self._adapter(name)
            action = next((a for a in adapter.resource.actions if a.name == action_name), None)
            if action is None or action.kind not in ("resource", "bulk"):
                raise AdminError(404, "Action not found", "not_found")
            await self._authorize(principal, name, "action:" + action_name)
            payload = await self._body(request)
            session = self.session_factory()
            try:
                if action.kind == "bulk":
                    ids = payload.get("ids")
                    if not isinstance(ids, list) or not ids or len(ids) > 100 or any(
                        not isinstance(value, (str, int)) or isinstance(value, bool) for value in ids
                    ) or len({str(value) for value in ids}) != len(ids):
                        raise AdminError(422, "Bulk actions require 1-100 distinct record IDs", "validation_error")
                    records = []
                    for identifier in ids:
                        record = await adapter.get(session, str(identifier), principal)
                        await self._authorize(principal, name, "action:" + action_name, record)
                        records.append(record)
                    remaining = {k: v for k, v in payload.items() if k != "ids"}
                    allowed = (await maybe_await(action.visible(principal, records))
                               if callable(action.visible) else action.visible)
                    if not allowed:
                        raise AdminError(403, "Action unavailable", "forbidden")
                    ctx = OperationContext("action", name, principal, session, action=action_name,
                                           records=records, payload=remaining)
                    await self._run_hooks(adapter, "before_action", ctx)
                    output = await maybe_await(action.handler(records, session, principal, ctx.payload))
                else:
                    allowed = (await maybe_await(action.visible(principal, None))
                               if callable(action.visible) else action.visible)
                    if not allowed:
                        raise AdminError(403, "Action unavailable", "forbidden")
                    ctx = OperationContext("action", name, principal, session, action=action_name,
                                           payload=payload)
                    await self._run_hooks(adapter, "before_action", ctx)
                    output = await maybe_await(action.handler(session, principal, ctx.payload))
                await self._run_hooks(adapter, "after_action", ctx)
                encoded = jsonable_encoder(output)
                self.log_event("action", "action.invoked", principal=principal,
                               resource=name, action=action_name, action_kind=action.kind)
                await self._publish(CollectionActionExecuted(
                    resource=name, actor_id=str(principal.id), action=action_name,
                    action_kind=action.kind, **event_context(),
                ))
                return {"result": encoded}
            finally:
                await maybe_await(session.close())

        @api.get("/api/resources/{name}/{identifier}")
        async def get_one(name: str, identifier: str, principal: Principal = Depends(self._principal)) -> dict:
            await self._authorize(principal, name, "show")
            session = self.session_factory()
            try:
                adapter = self._adapter(name)
                record = await adapter.get(session, identifier, principal)
                await self._authorize(principal, name, "show", record)
                return {"record": adapter.serialize(record, await self._allowed_fields(principal, name, view="show", record=record)),
                        "actions": await self._visible_actions(principal, name, record)}
            finally:
                await maybe_await(session.close())

        @api.patch("/api/resources/{name}/{identifier}")
        async def update_one(
            name: str, identifier: str, request: Request,
            principal: Principal = Depends(self._principal),
        ) -> Response:
            self._csrf(request)
            await self._authorize(principal, name, "edit")
            payload = await self._body(request)
            session = self.session_factory()
            try:
                adapter = self._adapter(name)
                record = await adapter.get(session, identifier, principal)
                await self._authorize(principal, name, "edit", record)
                self._require_version(adapter, record, request)
                write_fields = await self._allowed_fields(principal, name, edit=True, view="edit", record=record)
                rejected = set(payload) - write_fields
                if rejected:
                    if all(not adapter.writable(name) for name in rejected if name in adapter.columns) and all(
                        name in adapter.columns for name in rejected
                    ):
                        raise AdminError(422, "Unknown or read-only fields", "validation_error",
                                         {"fields": sorted(rejected)})
                    raise AdminError(403, "Cannot write one or more fields", "forbidden")
                ctx = OperationContext("update", name, principal, session, record=record,
                                       payload=payload.copy())
                await self._run_hooks(adapter, "before_update", ctx)
                ctx.payload = validate_payload(adapter.resource.edit_schema, ctx.payload)
                if set(ctx.payload) - write_fields:
                    raise AdminError(403, "Hook supplied unauthorized fields", "forbidden")
                await self._verify_foreign_keys(session, principal, adapter, ctx.payload, record=record)
                identity = adapter.record_identifier(record)
                changed = await adapter._stage_update(session, record, ctx.payload, principal, context=ctx)
                async with adapter._transaction_errors(session):
                    await maybe_await(session.flush())
                await maybe_await(session.refresh(record))
                if adapter.record_identifier(record) != identity:
                    raise AdminError(422, "Primary key components cannot be changed", "validation_error")
                if adapter.resource.update_handler is not None:
                    await self._verify_foreign_keys(session, principal, adapter,
                        {field: getattr(record, field) for field in adapter.foreign_key_fields & changed}, record=record)
                    if adapter.resource.scope is not None:
                        await adapter.get(session, identity, principal)
                read_fields = await self._allowed_fields(principal, name, view="show", record=record)
                response = JSONResponse({"record": adapter.serialize(record, read_fields)})
                await adapter._commit(session)
                await self._after_write(adapter, "after_update", ctx)
                self.log_event("resource", "resource.updated", principal=principal, resource=name,
                               record_id=identifier)
                if changed:
                    await self._publish(ResourceUpdated(
                        resource=name, record_id=identifier, actor_id=str(principal.id),
                        fields=field_refs(adapter, sorted(changed)), **event_context(),
                    ))
                return response
            finally:
                await maybe_await(session.close())

        @api.delete("/api/resources/{name}/{identifier}")
        async def delete_one(
            name: str, identifier: str, request: Request,
            principal: Principal = Depends(self._principal),
        ) -> dict:
            self._csrf(request)
            await self._authorize(principal, name, "delete")
            session = self.session_factory()
            try:
                adapter = self._adapter(name)
                has_uploads = adapter.resource._uploads_enabled
                if has_uploads:
                    await self._begin_upload_transaction(session, write=True)
                record = await adapter.get(session, identifier, principal, lock=True if has_uploads else None)
                await self._authorize(principal, name, "delete", record)
                self._require_version(adapter, record, request)
                ctx = OperationContext("delete", name, principal, session, record=record)
                await self._run_hooks(adapter, "before_delete", ctx)
                if has_uploads:
                    async with adapter._transaction_errors(session):
                        await maybe_await(session.execute(update(UploadEntry).where(
                            UploadEntry.resource == name,
                            UploadEntry.record_id == adapter.persisted_identifier(record, 120),
                        ).values(record_id=_PENDING_DELETE_RECORD)))
                await adapter.delete(session, record, principal)
                if has_uploads:
                    self._request_upload_cleanup()
                await self._run_hooks(adapter, "after_delete", ctx)
                self.log_event("resource", "resource.deleted", principal=principal, resource=name,
                               record_id=identifier)
                await self._publish(ResourceDeleted(
                    resource=name, record_id=identifier, actor_id=str(principal.id),
                    **event_context(),
                ))
                return {"ok": True}
            finally:
                await maybe_await(session.close())

        @api.post("/api/resources/{name}/{identifier}/actions/{action_name}")
        async def run_action(
            name: str, identifier: str, action_name: str, request: Request,
            principal: Principal = Depends(self._principal),
        ) -> dict:
            self._csrf(request)
            adapter = self._adapter(name)
            action = next((a for a in adapter.resource.actions if a.name == action_name), None)
            if action is None:
                raise AdminError(404, "Action not found", "not_found")
            await self._authorize(principal, name, "action:" + action_name)
            session = self.session_factory()
            try:
                record = await adapter.get(session, identifier, principal)
                await self._authorize(principal, name, "action:" + action_name, record)
                if action.kind != "record" or action_name not in await self._visible_actions(principal, name, record):
                    raise AdminError(403, "Action unavailable for this record", "forbidden")
                payload = await self._body(request)
                ctx = OperationContext("action", name, principal, session,
                                       record=record, action=action_name, payload=payload)
                await self._run_hooks(adapter, "before_action", ctx)
                output = await maybe_await(action.handler(record, session, principal, ctx.payload))
                await self._run_hooks(adapter, "after_action", ctx)
                encoded_output = jsonable_encoder(output)
                self.log_event("action", "action.invoked", principal=principal,
                               resource=name, action=action_name, record_id=identifier)
                await self._publish(ActionExecuted(
                    resource=name, record_id=identifier, actor_id=str(principal.id),
                    action=action_name, **event_context(),
                ))
                return {"result": encoded_output}
            finally:
                await maybe_await(session.close())

        async def _editable_relation(
            name: str, identifier: str, relation_name: str, principal: Principal,
            session: Any,
        ) -> tuple[MapperAdapter, Any, Any, MapperAdapter]:
            adapter = self._adapter(name)
            prop = adapter.relations.get(relation_name)
            config = adapter.resource.relationships.get(relation_name)
            target_name = adapter._related_resource(prop, self.resources) if prop else None
            if (prop is None or not prop.uselist or prop.secondary is None or prop.viewonly
                    or config is not None and not config.visible or target_name is None):
                raise AdminError(404, "Editable many-to-many relationship not found", "not_found")
            await self._authorize(principal, name, "edit")
            await self._authorize(principal, name, "show")
            # Eager loading is mandatory for SQLAlchemy AsyncSession.
            from sqlalchemy.orm import selectinload
            relationship_attr = getattr(adapter.resource.model, relation_name)
            statement = await adapter._scope(select(adapter.resource.model).options(
                selectinload(relationship_attr)).where(
                    adapter.identity_predicate(identifier)), principal)
            parent = (await maybe_await(session.execute(statement))).scalar_one_or_none()
            if parent is None:
                raise AdminError(404, "Record not found", "not_found")
            await self._authorize(principal, name, "edit", parent)
            return adapter, prop, parent, self._adapter(target_name)

        @api.post("/api/resources/{name}/{identifier}/relationships/{relation_name}/attach")
        async def attach_relation(name: str, identifier: str, relation_name: str,
                                  request: Request, principal: Principal = Depends(self._principal)) -> dict:
            self._csrf(request)
            payload = await self._body(request)
            if set(payload) != {"id"} or not isinstance(payload["id"], (int, str)) or isinstance(payload["id"], bool):
                raise AdminError(422, "Expected a related record ID", "validation_error")
            session = self.session_factory()
            try:
                parent_adapter, prop, parent, target = await _editable_relation(
                    name, identifier, relation_name, principal, session)
                await self._authorize(principal, target.resource.name, "select")
                related = await target.get(session, str(payload["id"]), principal)
                await self._authorize(principal, target.resource.name, "select", related)
                members = getattr(parent, relation_name)
                if not any(target.identity_values(row) == target.identity_values(related) for row in members):
                    members.append(related)
                    await parent_adapter._commit(session)
                    await self._publish(ResourceUpdated(
                        resource=name, record_id=identifier, actor_id=str(principal.id),
                        fields=(FieldRef(
                            name=relation_name, kind="relationship"),), **event_context(),
                    ))
                return {"ok": True}
            finally:
                await maybe_await(session.close())

        @api.post("/api/resources/{name}/{identifier}/relationships/{relation_name}/detach")
        async def detach_relation(name: str, identifier: str, relation_name: str,
                                  request: Request, principal: Principal = Depends(self._principal)) -> dict:
            self._csrf(request)
            payload = await self._body(request)
            if set(payload) != {"id"} or not isinstance(payload["id"], (int, str)) or isinstance(payload["id"], bool):
                raise AdminError(422, "Expected a related record ID", "validation_error")
            session = self.session_factory()
            try:
                parent_adapter, prop, parent, target = await _editable_relation(
                    name, identifier, relation_name, principal, session)
                await self._authorize(principal, target.resource.name, "select")
                members = getattr(parent, relation_name)
                scoped = await target.get(session, str(payload["id"]), principal)
                await self._authorize(principal, target.resource.name, "select", scoped)
                match = next((row for row in members if target.identity_values(row) == target.identity_values(scoped)), None)
                if match is None:
                    raise AdminError(404, "Relationship link not found", "not_found")
                members.remove(match)
                await parent_adapter._commit(session)
                await self._publish(ResourceUpdated(
                    resource=name, record_id=identifier, actor_id=str(principal.id),
                    fields=(FieldRef(
                        name=relation_name, kind="relationship"),), **event_context(),
                ))
                return {"ok": True}
            finally:
                await maybe_await(session.close())

        @api.post("/api/resources/{name}/{identifier}/relationships/{relation_name}/create", status_code=201)
        async def create_related(name: str, identifier: str, relation_name: str,
                                 request: Request, principal: Principal = Depends(self._principal)) -> Response:
            self._csrf(request)
            payload = await self._body(request)
            session = self.session_factory()
            try:
                _, _, parent, target = await _editable_relation(
                    name, identifier, relation_name, principal, session)
                await self._authorize(principal, target.resource.name, "create")
                await self._authorize(principal, target.resource.name, "select")
                response = await self._create_record(
                    session, target, principal, payload, members=getattr(parent, relation_name))
                await self._publish(ResourceUpdated(
                    resource=name, record_id=identifier, actor_id=str(principal.id),
                    fields=(FieldRef(
                        name=relation_name, kind="relationship"),), **event_context(),
                ))
                return response
            finally:
                await maybe_await(session.close())

        @api.get("/api/resources/{name}/{identifier}/relationships/{relation_name}")
        async def related(
            name: str, identifier: str, relation_name: str,
            offset: int = 0, limit: int = 20, q: str = "",
            principal: Principal = Depends(self._principal),
        ) -> dict:
            if offset < 0 or limit < 1:
                raise AdminError(422, "Invalid pagination", "validation_error")
            await self._authorize(principal, name, "show")
            adapter = self._adapter(name)
            prop = adapter.relations.get(relation_name)
            config = adapter.resource.relationships.get(relation_name)
            if config is not None and not config.visible:
                raise AdminError(404, "Relationship not available", "not_found")
            target_name = adapter._related_resource(prop, self.resources) if prop else None
            if target_name is None:
                raise AdminError(404, "Relationship not registered", "not_found")
            await self._authorize(principal, target_name, "list")
            session = self.session_factory()
            try:
                record = await adapter.get(session, identifier, principal)
                await self._authorize(principal, name, "show", record)
                return await adapter.relation(
                    session, principal, record, relation_name,
                    self._adapter(target_name), offset, limit, query=q,
                    allowed_fields=await self._allowed_fields(principal, target_name, view="list"),
                    per_record_fields=lambda row: self._allowed_fields(
                        principal, target_name, view="list", record=row),
                )
            finally:
                await maybe_await(session.close())

        @api.get("/{asset_path:path}", include_in_schema=False)
        async def spa(asset_path: str, request: Request) -> Any:
            dist = self._dist()
            if not (dist / "index.html").is_file():
                return JSONResponse(
                    status_code=503,
                    content={"error": {"code": "ui_not_built", "message":
                        "Pyntral SPA assets are missing. Install an official wheel or build custom UI with: pyntral build"}},
                )
            if asset_path.startswith("assets/") or asset_path in ("favicon.svg",):
                candidate = (dist / asset_path).resolve()
                if not candidate.is_relative_to(dist) or not candidate.is_file():
                    raise AdminError(404, "Asset not found", "not_found")
                return FileResponse(candidate)
            if "." in Path(asset_path).name:
                raise AdminError(404, "Asset not found", "not_found")
            html = (dist / "index.html").read_text(encoding="utf-8")
            mount = quote(request.scope.get("root_path", self.path).rstrip("/") + "/", safe="/")
            html = html.replace('<base data-pyntral-base href="./"', f'<base data-pyntral-base href="{mount}"', 1)
            return HTMLResponse(html, headers={"Cache-Control": "no-store"})

        @api.get("/", include_in_schema=False)
        async def spa_root(request: Request) -> Any:
            return await spa("", request)

    async def _body(self, request: Request, *, max_bytes: int | None = None) -> dict:
        limit = self.max_json_bytes if max_bytes is None else min(self.max_json_bytes, max_bytes)
        content = bytearray()
        async for chunk in request.stream():
            if len(content) + len(chunk) > limit:
                raise AdminError(413, "JSON input too large", "request_too_large")
            content.extend(chunk)
        try:
            body = json.loads(content)
        except (ValueError, RecursionError):
            raise AdminError(422, "Expected JSON", "validation_error") from None
        if not isinstance(body, dict):
            raise AdminError(422, "Expected JSON object", "validation_error")
        return body
