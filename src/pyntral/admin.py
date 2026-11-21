"""FastAPI integration and secured REST contract for the React frontend."""

from __future__ import annotations

import hmac
from contextlib import asynccontextmanager
import json
import re
import os
import secrets
import time
import uuid
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from starlette.middleware.sessions import SessionMiddleware

from .auth import AuthBackend, Principal, maybe_await
from .events import (
    AdminEvent, EventTransport, InMemoryEventBus, ResourceCreated, ResourceUpdated, ResourceDeleted,
    ActionExecuted, LoginSucceeded, LoginFailed, LogoutSucceeded, field_refs, event_context,
)
from .orm import AdminError, MapperAdapter
from .resources import Page, Resource, NavigationGroup, validate_navigation
from .bridge import Bridge, BridgeContext
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
        dist_dir: str | Path | None = None,
        title: str = "Pyntral",
        theme: dict[str, Any] | None = None,
        default_theme: str = "system",  # system | light | dark
        animations: bool = True,
        show_dashboard: bool = True,
        role_weights: dict[str, int] | None = None,
        logging_config: LoggingConfig | None = None,
        event_bus: EventTransport | None = None,
        auto_start_events: bool = True,
    ):
        if not isinstance(secret_key, str) or len(secret_key) < 32:
            raise ValueError("secret_key must contain at least 32 characters")
        if not path.startswith("/") or path == "/" or path.endswith("/"):
            raise ValueError("path must look like /admin (no trailing slash)")
        if auth is None:
            raise ValueError("An authentication backend is required")
        self.session_factory = session_factory
        self.auth = auth
        self.path = path
        self.title = title
        self.resources: dict[str, MapperAdapter] = {}
        self.pages: dict[str, Page] = {}
        self.groups: dict[str, NavigationGroup] = {}
        self.bridges: dict[str, Bridge] = {}
        self.events = event_bus if event_bus is not None else InMemoryEventBus()
        if auto_start_events:
            # Mounted sub-app lifespans are not driven by Starlette. Compose the
            # existing *parent* lifespan instead of using the removed FastAPI
            # add_event_handler() API or deprecated startup/shutdown callbacks.
            # This also preserves lifespan contexts supplied by host applications.
            previous_lifespan = app.router.lifespan_context
            event_transport = self.events

            @asynccontextmanager
            async def admin_events_lifespan(host_app: FastAPI):
                async with previous_lifespan(host_app):
                    await event_transport.start()
                    try:
                        yield
                    finally:
                        await event_transport.close()

            app.router.lifespan_context = admin_events_lifespan
        if default_theme not in ("light", "dark", "system"):
            raise ValueError("default_theme must be system, light or dark")
        self.theme = theme or {}
        self.default_theme = default_theme
        self.animations = animations
        self.show_dashboard = show_dashboard
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
            session_cookie="pyntral_session",
            max_age=60 * 60 * 12,
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
            report = await self.events.publish(event)
            self.log_event("events", "events.published", level="DEBUG",
                           event_type=event.type, event_id=event.event_id,
                           resource=event.resource, correlation_id=event.correlation_id,
                           field_names=[field.name for field in event.fields])
            if report.failed:
                self.log_event("events", "events.subscriber_failed", level="ERROR",
                               event_type=event.type, failed=report.failed)
        except Exception:
            # Even a custom bus must not corrupt the result of an already committed write.
            self.log_event("events", "events.dispatch_failed", level="ERROR",
                           event_type=event.type)

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
            return adapter.serialize(record, await self._allowed_fields(principal, event.resource))
        finally:
            await maybe_await(session.close())

    def add_resource(self, resource: Resource | type) -> Resource:
        if isinstance(resource, type):
            resource = Resource(resource)
        validate_navigation(resource.navigation)
        adapter = MapperAdapter(resource)
        if resource.access:
            thresholds = [resource.access.read, resource.access.select, resource.access.write,
                          resource.access.create, resource.access.edit, resource.access.delete]
            unknown = [x for x in thresholds if x is not None and x not in self.role_weights]
            if unknown:
                raise ValueError(f"Unknown role threshold(s): {unknown}")
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
        # For older auth callbacks, selecting an option uses the same authorization as listing.
        auth_action = "list" if action == "select" else action
        return bool(await maybe_await(self.auth.authorize(principal, name, auth_action, record)))

    async def _allowed_fields(self, principal: Principal, name: str, *, edit: bool = False) -> set[str]:
        adapter = self._adapter(name)
        allowed = set()
        for field_name in adapter.columns:
            if not adapter.visible(field_name):
                continue
            field = adapter.resource.fields.get(field_name)
            role = field.write_role if edit and field else field.read_role if field else None
            if role is not None and not self._role_ok(principal, role):
                continue
            if edit and field is not None and field.read_role is not None and not self._role_ok(principal, field.read_role):
                continue
            if edit and not adapter.writable(field_name):
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
        return allowed

    async def _verify_foreign_keys(self, session: Any, principal: Principal,
                                   adapter: MapperAdapter, payload: dict) -> None:
        for prop in adapter.relations.values():
            if prop.direction.name != "MANYTOONE":
                continue
            target = adapter._related_resource(prop, self.resources)
            for field_name, col in adapter.columns.items():
                if field_name not in payload or not any(col is c for c in prop.local_columns):
                    continue
                if target is None or not await self._can(principal, target, "select"):
                    raise AdminError(403, "Related resource cannot be selected", "forbidden")
                if payload[field_name] is not None:
                    try:
                        await self._adapter(target).get(session, str(payload[field_name]), principal)
                    except AdminError as exc:
                        if exc.status == 404:
                            raise AdminError(409, "Related record is not selectable", "integrity_error") from None
                        raise

    async def _visible_actions(self, principal: Principal, name: str, record: Any) -> list[str]:
        adapter = self._adapter(name)
        visible = []
        for action in adapter.resource.actions:
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

    async def _principal(self, request: Request) -> Principal:
        raw = request.session.get("principal")
        if not isinstance(raw, dict):
            raise AdminError(401, "Sign in required", "unauthorized")
        try:
            identity = Principal(
                id=str(raw["id"]),
                username=str(raw["username"]),
                roles=list(raw.get("roles", [])),
                display_name=raw.get("display_name"),
                email=raw.get("email"),
                attributes=dict(raw.get("attributes") or {}),
            )
        except (KeyError, TypeError, ValueError):
            request.session.clear()
            raise AdminError(401, "Session invalid", "unauthorized") from None
        resolved = await maybe_await(self.auth.resolve(identity))
        if resolved is None:
            request.session.clear()
            raise AdminError(401, "Session expired", "unauthorized")
        return resolved

    def _csrf(self, request: Request) -> None:
        token = request.session.get("csrf")
        supplied = request.headers.get("X-CSRF-Token", "")
        if not isinstance(token, str) or not hmac.compare_digest(token, supplied):
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
                if request.url.path.startswith((self.path + "/api/", self.path + "/auth/")) or request.scope.get("path", "").startswith(("/api/", "/auth/")):
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

        @api.get("/auth/me")
        async def me(request: Request) -> dict:
            try:
                principal = await self._principal(request)
            except AdminError:
                return {"user": None, "csrf": None}
            return {"user": principal.as_dict(), "csrf": request.session.get("csrf")}

        @api.post("/auth/login")
        async def login(request: Request) -> dict:
            # Reject cross-origin browser form submission (login CSRF).
            origin = request.headers.get("origin")
            if origin:
                parsed = urlparse(origin)
                if parsed.netloc != request.url.netloc or parsed.scheme != request.url.scheme:
                    raise AdminError(403, "Cross-origin login rejected", "forbidden")
            try:
                payload = await request.json()
            except ValueError:
                raise AdminError(422, "Expected JSON", "validation_error") from None
            if not isinstance(payload, dict):
                raise AdminError(422, "Expected JSON object", "validation_error")
            username, password = payload.get("username"), payload.get("password")
            if not isinstance(username, str) or not isinstance(password, str) or len(username) > 320 or len(password) > 4096:
                raise AdminError(422, "Invalid credentials format", "validation_error")
            user = await maybe_await(self.auth.login(username, password))
            if user is None:
                self.log_event("auth", "auth.login_failed", level="WARNING")
                await self._publish(LoginFailed(**event_context()))
                raise AdminError(401, "Invalid username or password", "invalid_credentials")
            request.session.clear()
            request.session["principal"] = user.as_dict()
            request.session["csrf"] = secrets.token_urlsafe(32)
            self.log_event("auth", "auth.login_success", principal=user)
            await self._publish(LoginSucceeded(actor_id=str(user.id), **event_context()))
            return {"user": user.as_dict(), "csrf": request.session["csrf"]}

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
            request.session.clear()
            request.session["principal"] = user.as_dict()
            request.session["csrf"] = secrets.token_urlsafe(32)
            self.log_event("auth", "auth.login_success", principal=user)
            await self._publish(LoginSucceeded(actor_id=str(user.id), **event_context()))
            return {"user": user.as_dict(), "csrf": request.session["csrf"]}

        @api.post("/auth/logout")
        async def logout(request: Request, _principal: Principal = Depends(self._principal)) -> dict:
            self._csrf(request)
            request.session.clear()
            self.log_event("auth", "auth.logout", principal=_principal)
            await self._publish(LogoutSucceeded(actor_id=str(_principal.id), **event_context()))
            return {"ok": True}

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
                    metadata.update(fields=[], listFields=[], searchFields=[], relationships=[], actions=[])
                else:
                    read_fields = await self._allowed_fields(principal, name)
                    edit_fields = await self._allowed_fields(principal, name, edit=True)
                    metadata["fields"] = [f for f in metadata["fields"] if f["name"] in read_fields]
                    for field in metadata["fields"]:
                        field["readonly"] = (field["readonly"] or
                            not (metadata["capabilities"]["edit"] or metadata["capabilities"]["create"])
                            or field["name"] not in edit_fields)
                        if field["relation"] and not can_select.get(field["relation"]["resource"], False):
                            field["relation"] = None
                    metadata["listFields"] = [n for n in metadata["listFields"] if n in read_fields]
                    metadata["searchFields"] = [n for n in metadata["searchFields"] if n in read_fields]
                    metadata["relationships"] = [r for r in metadata["relationships"]
                        if can_read.get(r["resource"], False)]
                    metadata["actions"] = [a for a in metadata["actions"]
                        if await self._can(principal, name, "action:" + a["name"])]
                resources.append(metadata)
            visible_paths = [r["navigation"] for r in resources
                             if r["navigation"] and r["navigationState"] != "hidden"]
            pages = [{"name": p.name, "label": p.label, "component": p.component,
                      "icon": p.icon, "navigation": p.navigation, "navigationOrder": p.navigation_order}
                     for p in self.pages.values()
                     if (p.min_role is None or self._role_ok(principal, p.min_role))
                     and await maybe_await(self.auth.authorize(principal, "page:" + p.name, "view"))]
            visible_paths.extend(p["navigation"] for p in pages if p["navigation"])
            return {"title": self.title, "resources": resources,
                    "navigation": {"groups": [
                        {"path": g.path, "icon": g.icon, "order": g.order}
                        for g in self.groups.values() if any(
                            path == g.path or path.startswith(g.path + "/") for path in visible_paths
                        )], "showDashboard": self.show_dashboard},
                    "theme": {"default": self.default_theme,
                              "animations": self.animations,
                              "tokens": self.theme},
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
            payload = await self._body(request)
            try:
                parsed = bridge.input_model.model_validate(payload)
            except ValidationError as exc:
                raise AdminError(422, "Invalid bridge input", "validation_error", exc.errors(
                    include_url=False, include_context=False, include_input=False)) from None
            session = self.session_factory()
            try:
                output = await maybe_await(bridge.handler(parsed, BridgeContext(principal, session)))
                try:
                    validated = bridge.output_model.model_validate(output)
                except ValidationError as exc:
                    # Implementation error; do not leak arbitrary output content to clients.
                    raise AdminError(500, "Bridge output did not match its model", "bridge_output_error") from exc
                self.log_event("bridge", "bridge.invoked", principal=principal, bridge=name)
                return {"result": validated.model_dump(mode="json")}
            finally:
                await maybe_await(session.close())

        @api.get("/api/resources/{name}/options")
        async def options(name: str, q: str = "", ids: str = "", principal: Principal = Depends(self._principal)) -> dict:
            await self._authorize(principal, name, "select")
            session = self.session_factory()
            try:
                return {"items": await self._adapter(name).options(session, principal, q, ids=ids.split(",") if ids else None)}
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
                read_fields = await self._allowed_fields(principal, name)
                result = await adapter.list(
                    session, principal, offset=offset, limit=limit, q=params.get("q", ""),
                    sort=params.get("sort"), desc=params.get("desc") == "true", filters=filters,
                    allowed_fields=read_fields,
                )
                if adapter.resource.actions:
                    # Evaluated against the actual scoped ORM records; no frontend-only ACL.
                    result["actionsByRecord"] = {}
                    if result["items"]:
                        ids = [adapter.pk_value(str(item[adapter.pk_name])) for item in result["items"]]
                        stmt = await adapter._scope(select(adapter.resource.model).where(
                            getattr(adapter.resource.model, adapter.pk_name).in_(ids)), principal)
                        records = (await maybe_await(session.execute(stmt))).scalars().all()
                        for record in records:
                            result["actionsByRecord"][str(getattr(record, adapter.pk_name))] = (
                                await self._visible_actions(principal, name, record)
                            )
                return result
            finally:
                await maybe_await(session.close())

        @api.post("/api/resources/{name}", status_code=201)
        async def create(name: str, request: Request, principal: Principal = Depends(self._principal)) -> dict:
            self._csrf(request)
            await self._authorize(principal, name, "create")
            payload = await self._body(request)
            adapter = self._adapter(name)
            write_fields = await self._allowed_fields(principal, name, edit=True)
            rejected = set(payload) - write_fields
            if rejected:
                if all(not adapter.writable(name) for name in rejected if name in adapter.columns) and all(
                    name in adapter.columns for name in rejected
                ):
                    raise AdminError(422, "Unknown or read-only fields", "validation_error",
                                     {"fields": sorted(rejected)})
                raise AdminError(403, "Cannot write one or more fields", "forbidden")
            session = self.session_factory()
            try:
                await self._verify_foreign_keys(session, principal, adapter, payload)
                result = await adapter.create(session, payload)
                read_fields = await self._allowed_fields(principal, name)
                self.log_event("resource", "resource.created", principal=principal, resource=name,
                               record_id=result.get(adapter.pk_name))
                await self._publish(ResourceCreated(
                    resource=name, record_id=str(result[adapter.pk_name]), actor_id=str(principal.id),
                    fields=field_refs(adapter, payload), **event_context(),
                ))
                return {"record": {k: v for k, v in result.items() if k in read_fields}}
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
                return {"record": adapter.serialize(record, await self._allowed_fields(principal, name)),
                        "actions": await self._visible_actions(principal, name, record)}
            finally:
                await maybe_await(session.close())

        @api.patch("/api/resources/{name}/{identifier}")
        async def update_one(
            name: str, identifier: str, request: Request,
            principal: Principal = Depends(self._principal),
        ) -> dict:
            self._csrf(request)
            await self._authorize(principal, name, "edit")
            payload = await self._body(request)
            session = self.session_factory()
            try:
                adapter = self._adapter(name)
                record = await adapter.get(session, identifier, principal)
                await self._authorize(principal, name, "edit", record)
                write_fields = await self._allowed_fields(principal, name, edit=True)
                rejected = set(payload) - write_fields
                if rejected:
                    if all(not adapter.writable(name) for name in rejected if name in adapter.columns) and all(
                        name in adapter.columns for name in rejected
                    ):
                        raise AdminError(422, "Unknown or read-only fields", "validation_error",
                                         {"fields": sorted(rejected)})
                    raise AdminError(403, "Cannot write one or more fields", "forbidden")
                await self._verify_foreign_keys(session, principal, adapter, payload)
                before = {field_name: getattr(record, field_name) for field_name in payload}
                result = await adapter.update(session, record, payload)
                changed = [field_name for field_name, old in before.items()
                           if old != getattr(record, field_name)]
                read_fields = await self._allowed_fields(principal, name)
                self.log_event("resource", "resource.updated", principal=principal, resource=name,
                               record_id=identifier)
                if changed:
                    await self._publish(ResourceUpdated(
                        resource=name, record_id=identifier, actor_id=str(principal.id),
                        fields=field_refs(adapter, changed), **event_context(),
                    ))
                return {"record": {k: v for k, v in result.items() if k in read_fields}}
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
                record = await adapter.get(session, identifier, principal)
                await self._authorize(principal, name, "delete", record)
                await adapter.delete(session, record)
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
                if action_name not in await self._visible_actions(principal, name, record):
                    raise AdminError(403, "Action unavailable for this record", "forbidden")
                payload = await self._body(request)
                output = await maybe_await(action.handler(record, session, principal, payload))
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
                    allowed_fields=await self._allowed_fields(principal, target_name),
                )
            finally:
                await maybe_await(session.close())

        @api.get("/{asset_path:path}", include_in_schema=False)
        async def spa(asset_path: str) -> Any:
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
            return FileResponse(dist / "index.html", headers={"Cache-Control": "no-store"})

        @api.get("/", include_in_schema=False)
        async def spa_root() -> Any:
            return await spa("")

    @staticmethod
    async def _body(request: Request) -> dict:
        try:
            body = await request.json()
        except ValueError:
            raise AdminError(422, "Expected JSON", "validation_error") from None
        if not isinstance(body, dict):
            raise AdminError(422, "Expected JSON object", "validation_error")
        return body
