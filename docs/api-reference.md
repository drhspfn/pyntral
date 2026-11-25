# Python and HTTP API reference

[Documentation index](README.md) · [Resources](resources.md) · [Authentication](authentication.md)

This page summarizes the public interfaces available in the current beta. For precise parameter and TypeScript signatures, source code is authoritative: [`src/pyntral/`](../src/pyntral/) and [`src/pyntral/ui/src/types.ts`](../src/pyntral/ui/src/types.ts).

## Public Python imports

```python
from pyntral import (
    Admin, Resource, CrudLayout, Field, Relationship, Action, Page, NavigationGroup,
    SidebarConfig, SidebarHeader, SidebarFooter, SvgIcon, ImageIcon, IconSpec, LoginConfig,
    RoleAccess, Bridge, BridgeContext, BridgeUpload, BridgeFile, ResourceHook, OperationContext, VirtualField, FieldDependency,
    FieldView, LayoutSection, JobAction, PasswordFeature, SoftDeleteFeature,
    TimestampFeature, AuditFeature, UploadFeature, LocalStorage, S3Storage,
    Principal, CallbackAuth, LocalAuth, ModelAuth, hash_password, verify_password,
    SessionStore, SessionIdentity, MemorySessionStore,
    LoggingConfig, EventFormatter, configure_logging, forward_to_loguru, stop_logging,
    AdminEvent, FieldRef, ResourceEvent, ResourceCreated, ResourceUpdated,
    ResourceDeleted, ActionExecuted, LoginSucceeded, LoginFailed, LogoutSucceeded,
    CustomEvent, InMemoryEventBus, EventBus, EventTransport, DeliveryReport,
    RabbitMQEventBus, KafkaEventBus,
)
```

### `Admin` constructor

```python
Admin(
    app,
    *, session_factory, auth, secret_key,
    path="/admin", secure_cookie=True, session_cookie="pyntral_session",
    session_cookie_path="/", session_max_age=43200, session_store=None,
    require_async_sessions=False, enable_jobs=True, dist_dir=None,
    title="Pyntral", favicon=None, theme=None, default_theme="system",
    animations=True, show_dashboard=True, dashboard_component=None, sidebar=None, login=None, role_weights=None,
    logging_config=None, event_bus=None, auto_start_events=True,
    event_publish_timeout=2.0, max_json_bytes=1048576, storage=None,
    default_locale="en", translations=None, locale_resolver=None,
    theme_resolver=None, realtime_updates=False,
)
```

Key methods:

| Method | Description |
| --- | --- |
| `add_resource(Resource(...) | Model)` | Introspect and register a mapped resource. |
| `add_page(Page(...))` | Register a custom React page. |
| `add_group(NavigationGroup(...))` | Add a nested sidebar group. |
| `add_bridge(Bridge(...))` | Register a Pydantic-validated RPC handler. |
| `log_event(channel, event, level="INFO", **fields)` | Emit a structured package log event under policy. |
| `read_event_record(event, principal)` | Authorization-scoped read of the record referenced by an event. |
| `events.on(...)`, `events.subscribe(...)` | Register event subscribers. |

### Configuration types

- `Resource`: model, name, label, icon, navigation/order, list/search fields, field overrides, actions, page size, title/visible label, relationship settings, layouts, crud_views, crud_slots, crud_layouts, create_handler, update_handler, hooks, scope, access policy and CRUD capability flags. See [resources](resources.md).
- `Field`: label, visible, readonly, required, widget, help, options, components, span, read/write roles, filter operators and width.
- `Relationship`: visible, label, selectable, layout (`table`/`cards`).
- `Action`: name, handler, label, variant, confirmation, position, appearance, component, dialog, icon, visible.
- `Page`: name, label, component, icon, navigation, order, min_role.
- `NavigationGroup`: path, icon, order, optional component (dashboard registry ID) and min_role (landing page only).
- `RoleAccess`: read/select/write/create/edit/delete thresholds and navigation state.
- `Bridge`: name, input_model, output_model, handler, description, min_role, optional upload.
- `BridgeUpload`: max_bytes (default 5 MiB, range 1–64 MiB), content_types (default application/octet-stream; exact types or type/*).
- `BridgeFile`: filename, content_type, content (bytes). BridgeContext.file is None for JSON bridges.
- `OperationContext`: operation, resource, principal, session, record, payload, action, records.
- `Principal`: id, username, roles, display_name, email, attributes; `as_dict()` includes `name`/`role`.
- `LoggingConfig`: level, channels, events, http, slow_request_ms and optional principal/record identifiers.
- Event classes: immutable metadata-only Pydantic envelopes; buses implement `EventTransport` lifecycle and publication.

### Sidebar and icon configuration

`Admin(sidebar=SidebarConfig(...))` is optional. Omission uses the defaults
below. The generic wheel reads this metadata without a custom SPA build.

| `SidebarConfig` parameter | Default | Meaning |
| --- | --- | --- |
| `width`, `min_width`, `max_width` | 238, 238, 420 | Desktop width in pixels; 160 ≤ min ≤ width ≤ max ≤ 640. Further clamped to available viewport width. |
| `mobile_width` | 238 | Independent drawer width (160–480 px), constrained to the viewport. |
| `resizable` | True | Enable desktop resize separator. |
| `show_icons` | True | Show navigation glyphs, independent of header and lock/disclosure indicators. |
| `show_search` | False | Enable search over the authorized navigation tree. |
| `search_placeholder` | None | Optional search text; None uses the UI locale. |
| `icon_size` | 16 | Navigation glyph size, 12–32 px. |
| `indent` | 9 | Indentation per level, 0–24 px. |
| `max_indent_depth` | 5 | Maximum visual indentation level, 0–8; does not restrict tree depth. |
| `dashboard_icon` | "layout-dashboard" | IconSpec for Overview. |
| `header`, `footer` | SidebarHeader(), SidebarFooter() | Region configuration; None hides the built-in region. |
| `header_component`, `footer_component`, `item_component` | None | Optional registered TSX extension IDs. |

| `SidebarHeader` parameter | Default | Meaning |
| --- | --- | --- |
| `title` | None | Inherit Admin.title. |
| `subtitle` | None | Secondary text. |
| `icon` | "command" | IconSpec for the logo. |
| `show_icon`, `show_title`, `show_subtitle` | True | Independent visibility switches. |
| `align` | "left" | left, center, right. |
| `direction` | "horizontal" | horizontal or vertical. |
| `divider` | True | Border below header. |
| `icon_size` | 24 | Logo height / glyph size (12–120 px). |
| `logo_width` | None | Optional image width (12–420 px). |
| `icon_background` | True | Themed icon background. |
| `link_to_dashboard` | True | Header navigates to Overview when Dashboard is enabled. |

`SidebarFooter(show_user=True, show_avatar=True, show_roles=True, divider=True)`
controls the built-in account region. A TSX extension may still render its
own content when the default region is hidden.

`IconSpec = str | SvgIcon | ImageIcon | None` is accepted by
`Resource.icon`, `Page.icon`, `NavigationGroup.icon`, `Action.icon`,
`SidebarHeader.icon` and `SidebarConfig.dashboard_icon`.

- String: lowercase kebab-case Lucide name; unknown names fall back in the UI.
- `SvgIcon(svg: str)` / `SvgIcon.from_file(path)`: SVG XML up to 128 KiB, without DOCTYPE/entity declarations, displayed as an image rather than inline markup.
- `ImageIcon(src=None, light=None, dark=None)`: at least one HTTP(S) or relative image URL; theme-specific sources override the generic source.
- `None`: no icon.

See [UI configuration](ui.md#sidebar-branding-and-navigation-icons) and
[TSX extension contracts](extensions.md#sidebar-extensions) for complete examples.

### Login configuration

`Admin(login=LoginConfig(...))` configures the standard unauthenticated
screen. The default is a single centered card.

| Parameter | Default | Meaning |
| --- | --- | --- |
| `layout` | "centered" | centered or split. |
| `side_position` | "left" | Position of the optional split panel (left/right). |
| `brand_position` | "auto" | auto, form, side, hidden; side requires split. |
| `brand` | None | Inherit SidebarHeader or override it with another SidebarHeader. |
| `brand_align`, `brand_direction` | None | Override brand alignment/direction; auto uses left/horizontal on side and form alignment/vertical in the form. |
| `form_align` | "center" | Form heading alignment (left/center/right); fields remain left-aligned. |
| `card` | True | Show card surface, border and shadow; False gives a flat form. |
| `max_width` | 420 | Card/form maximum width, 280–640 px. |
| `title` | "Sign in" | Form heading. |
| `subtitle` | "Use your administrator account to continue." | Optional description. |
| `eyebrow`, `form_icon` | None | Optional extra heading text and IconSpec glyph. |
| `username_label`, `password_label`, `submit_label` | "Username", "Password", "Continue" | Form and submit labels. |
| `footer` | None | Optional text beneath the form. |
| `side_title`, `side_description`, `side_footer` | None | Optional content in the split panel. |
| `show_theme_toggle`, `show_password_toggle` | True | Independent theme and password visibility controls. |

On mobile, a split layout becomes a single form, with side branding moved
into it. If the sidebar header is disabled and no login brand is specified,
the fallback brand uses Admin.title. To suppress all branding use
`brand_position="hidden"`. See [login customization](ui.md#login-screen-customization).

## HTTP endpoints

All paths below are relative to `Admin.path` (default `/admin`). Except for
session discovery, public login presentation, login, token exchange and static assets, the endpoints
require an authenticated session. Resource mutations, bridge calls and logout
require CSRF protection.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/auth/config` | Public login presentation, global theme and login localization. |
| GET | `/auth/me` | Session state and CSRF token. |
| POST | `/auth/login` | Username/password authentication. |
| POST | `/auth/external` | Exchange a token verified by the configured auth callback. |
| POST | `/auth/logout` | End session (CSRF protected). |
| GET | `/api/schema` | Access-filtered resource, page, bridge, navigation/sidebar, theme metadata. |
| GET | `/api/resources/{name}` | List, sort, search and filter records. |
| POST | `/api/resources/{name}` | Create a record (CSRF protected). |
| GET | `/api/resources/{name}/options` | Searchable `{value,label}` options, including `ids` lookup. |
| GET | `/api/resources/{name}/export` | Bounded CSV or JSON export using the resource query and allowed columns. |
| GET | `/api/resources/{name}/{id}` | Read a record with available actions. |
| PATCH | `/api/resources/{name}/{id}` | Update a record (CSRF protected). |
| DELETE | `/api/resources/{name}/{id}` | Delete a record (CSRF protected). |
| POST | `/api/resources/{name}/{id}/actions/{action}` | Execute a record action (CSRF protected). |
| POST | `/api/resources/{name}/actions/{action}` | Execute a resource or bulk action. |
| GET | `/api/resources/{name}/{id}/relationships/{relation}` | Paginated related collection. |
| POST | `/api/resources/{name}/{id}/relationships/{relation}/{attach\|detach\|create}` | Attach, detach or create a record in an editable many-to-many relationship. |
| GET, POST | `/api/resources/{name}/{id}/uploads` | List attachments or upload a binary request body. |
| GET, DELETE | `/api/uploads/{upload_id}` | Download or remove an attachment. |
| POST | `/api/resources/{name}/jobs/{job_name}` | Start a registered background job when enabled. |
| GET, DELETE | `/api/jobs/{job_id}` | Read a job's progress or cancel it. |
| GET | `/api/realtime` | SSE invalidations when enabled. |
| POST | `/api/bridge/{name}` | Pydantic-validated RPC (CSRF protected). |
| GET | `/`, `/{asset_path:path}` | Production SPA assets and history fallback. |

### Public GET /auth/config

This endpoint is intentionally unauthenticated and returns only presentation
metadata: `title`, `login`, `theme`, and `localization`. It uses the same theme shape as
the authenticated schema (`default`, `animations`, `tokens.light`,
`tokens.dark`) but does not evaluate per-principal resolvers. Login metadata
uses camelCase versions of the parameters above, with the brand resolved to
the shared sidebar header shape and auto position resolved to form or side.
Only translation keys prefixed `login.` are exposed. Do not place secrets in
global theme, login text, logos or public login translations. Responses are
marked no-store. The resource schema remains authenticated.

### Sidebar metadata in GET /api/schema

`navigation.sidebar` uses camelCase keys:
`width`, `minWidth`, `maxWidth`, `mobileWidth`, `resizable`, `showIcons`,
`iconSize`, `indent`, `maxIndentDepth`, `dashboardIcon`, `showSearch`, `searchPlaceholder`, `header`, `footer`,
`headerComponent`, `footerComponent`, `itemComponent`.
The header includes `title`, `subtitle`, `icon`, `showIcon`, `showTitle`,
`showSubtitle`, `align`, `direction`, `divider`, `iconSize`, `logoWidth`,
`iconBackground`, `linkToDashboard`. The footer contains `showUser`,
`showAvatar`, `showRoles`, `divider`. Hidden regions are null.

All icon fields use the same wire representation:

```json
"shopping-cart"
```

```json
{"kind":"svg","svg":"<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 24 24\"><path d=\"M0 0L24 24\"/></svg>"}
```

```json
{"kind":"image","src":"/static/logo.png","light":null,"dark":null}
```

A null icon has no glyph. Metadata is presentation only; server authorization
remains independent of the sidebar.

Resources with attachments expose `uploads: true` and `uploadMaxBytes` in
their schema. GET on a record's uploads endpoint returns
`{"items":[{"id":"...","filename":"...","content_type":"image/png","size_bytes":123}]}`.
A successful POST returns HTTP 201 with `id`, `filename` and `size_bytes`.
Downloads remain authenticated and are served as attachments.

### List endpoint

Supported query parameters: `offset`, `limit`, `sort`, `desc=true|false`, quick search `q`, and `filter.FIELD.OPERATOR`. Examples:

```http
GET /admin/api/resources/products?offset=0&limit=20&sort=id&desc=true
GET /admin/api/resources/products?filter.price.between=%7B%22from%22%3A10%2C%22to%22%3A90%7D
```

The response includes `items`, `total`, and may include `actionsByRecord`; exact records and fields depend on permissions. Filtering syntax and bounds are documented in [filters](filters.md). Related options use `q=...` and `ids=1,2` and return `{ "items": [{ "value": ..., "label": ... }] }`.

### Mutation formats

- `POST /api/resources/{name}`: JSON column values; success returns `201` and `{ "record": { ... } }`.
- `PATCH /api/resources/{name}/{id}`: partial JSON column values; success returns `{ "record": { ... } }`.
- `DELETE /api/resources/{name}/{id}`: returns `{ "ok": true }`.
- Actions return a JSON result from the handler wrapped by the API; consult the example and actual route code if building a custom client.
- JSON bridges accept a Pydantic input object; binary bridges accept raw bytes with X-Filename and X-Pyntral-Input headers. Both return `{ "result": ... }`. See [binary RPC](bridges.md#binary-uploads-with-typed-rpc).
- Versioned resources require `If-Match` for PATCH and DELETE. A missing version returns HTTP 428 and a stale one returns HTTP 412.
- Attachment POST accepts a binary body, an optional `X-Filename` header and a content type. See [upload limits and storage](resources.md#secure-resource-uploads).

### Error handling

Errors have a structured `error` object with a machine-readable code and message. Common statuses: `401` (not authenticated), `403` (forbidden/CSRF), `404` (unknown record/resource), `409` (constraint conflict), `422` (invalid input/filter), `500` (unhandled server failure). Do not parse messages for business logic; use status/code.

The bundle's `@pyntral/api` helper attaches same-origin cookies and the CSRF token and raises `ApiError(status, code, message, details)`. Direct external calls to admin endpoints need a valid session and CSRF token.

## Events and output serialization

Events include a stable event ID, UTC timestamp, optional correlation and actor IDs, resource and record identifiers, and fields containing only field names and schema kinds. They are versioned for broker transport in [`transports/base.py`](../src/pyntral/transports/base.py).

See [events](events.md) for the delivery/ACK contract and [bridges](bridges.md) for automatically generated TypeScript DTO bindings.

## Consumer extension APIs

- `Resource(crud_slots={"list": {"before": "component"}, "show": {"after": "component"}})`: additive CRUD extensions, alongside the existing `crud_views`; see [composition](extensions.md#compose-standard-crud-views).
- `Resource(create_handler=callback, update_handler=callback)`: transactional domain handlers receiving `OperationContext`; see [custom writes](resources.md#custom-transactional-writes).
- Composite-key resources expose `primaryKeys: string[]`, `primaryKey: "__pyntral_id"` and opaque row IDs for CRUD operations; see [composite keys](resources.md#composite-primary-keys).
- `Bridge(upload=BridgeUpload(max_bytes=..., content_types=(...)))`: opt-in raw binary input with typed metadata; `BridgeContext.file` is a `BridgeFile` or None. See [binary uploads](bridges.md#binary-uploads-with-typed-rpc).
- Public React components: `Tabs`, `TabList`, `Tab`, `TabPanel`, `Table`, `DataTable`. See [UI reference](ui.md#tabs-and-tables).

### Browser branding and HTTP client

`Admin(favicon=SvgIcon | Path | None)` accepts a configured SVG or SVG/PNG/ICO
file and inherits the sidebar SVG if omitted. `GET /auth/config` also exposes
the public application `title`. `GET /auth/favicon` serves the image; the
legacy `/favicon.svg` route remains available. See [browser branding](ui.md#browser-title-and-favicon).

`@pyntral/api` exports `api<T>`, `ApiError`, `buildQuery`, `base`, and the `ApiOptions` type.
See [HTTP client](extensions.md#http-client-pyntralapi) for admin and host
scope and security details.

### Navigation and dashboard metadata

`Admin(dashboard_component="home")` references a TSX ID in the
`dashboards` manifest category. `NavigationGroup(component="category",
min_role=None)` configures an authorized category landing page.
`SidebarConfig(show_search=False, search_placeholder=None)` controls
navigation filtering. Authenticated schema exposes navigation.dashboardComponent
and per-group component IDs only when permitted; sidebar.showSearch and
sidebar.searchPlaceholder configure the search. React `DashboardProps`, `DashboardComponent`, `NavigationGroupDef`,
`CrudLayoutDef`, `CrudMode`, `CodeBlockProps` and `JsonViewProps` are public
through `@pyntral/types` (navigation/layout) or `@pyntral/ui` (code viewers). See [dashboards](extensions.md#home-and-category-dashboards)
and [code viewers](ui.md#codeblock-and-jsonview).

### CRUD presentation layout

`Resource(crud_layouts={"list": {"show_heading": False}})` hides the stock
title and description on the list, not its actions. `CrudLayout` is a public
TypedDict; supported modes are list/create/edit/show. `before_position`
accepts "after_heading" (default) or "above_heading". Schema uses
`crudLayouts[mode].showHeading` and `beforePosition`.
See [heading visibility and slots](extensions.md#heading-visibility-and-slot-placement).
