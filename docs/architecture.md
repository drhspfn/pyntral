# Architecture

[Documentation index](README.md)

Pyntral is a FastAPI sub-application mounted at `Admin.path` (default `/admin`). It serves a compiled React SPA and exposes JSON endpoints for metadata, CRUD, relationships, actions, authentication, and typed bridges. The host application keeps ownership of SQLAlchemy connections and business logic.

## Components

| Layer | Responsibility | Location |
| --- | --- | --- |
| `Admin` | Registries, security, route mounting, event lifecycle | `src/pyntral/admin.py` |
| `Resource`, `Field`, `Action`, `Page` | Declarative resource configuration | `src/pyntral/resources.py` |
| `MapperAdapter` | Introspection, serialization, validation, filtering, CRUD | `src/pyntral/orm.py` |
| Auth backends | Session identities and permission callbacks | `src/pyntral/auth.py` |
| Event buses | Metadata-only events and broker delivery | `src/pyntral/events.py`, `transports/` |
| UI package | React/TypeScript components, routing, state, CSS | `src/pyntral/ui/` |
| CLI | Vite workspace, type generation, build cache, dev servers | `src/pyntral/cli.py` |

## Request flow

1. The browser authenticates through `/admin/auth/login` (or a custom token exchange). The server issues a signed session cookie and a CSRF token.
2. The React SPA fetches `/admin/api/schema`, containing resources, allowed capabilities, display fields, navigation and theme settings.
3. CRUD requests go to registry-backed endpoints. The server resolves the current principal, checks role and callback permissions, validates values, applies the resource scope, and uses SQLAlchemy sessions.
4. After a successful database commit, metadata-only CRUD events are sent to `admin.events`. Custom actions have separate success events, subject to their own transaction logic.
5. React uses TanStack Query to cache records and refresh UI state after mutations. Custom TSX modules are compiled into the SPA during a Vite build.

## Build/runtime separation

The Python resource registry is dynamic. Registering a new model or changing its fields changes the JSON schema returned by the backend and does not require a JavaScript rebuild. By contrast, changing a TSX extension or theme component changes the client bundle; `pyntral dev` uses HMR, and `pyntral build` creates the production bundle.

The generic SPA is bundled as static package data inside published Python wheels and is available without npm. Only an application with custom TSX components needs an application-local Vite build; that bundle takes precedence over the generic one.

The `.pyntral/` directory stores generated UI sources, npm installation data, generated bridge types, fingerprints, and compiled assets. It is ignored by Git and can be removed and reconstructed.

## Extension and security boundaries

Custom React components run in the browser. They may call authenticated HTTP APIs or generated Pydantic bridge methods, but do not have direct access to Python functions or SQLAlchemy sessions. Server-side permissions must be enforced by `AuthBackend.authorize`, `RoleAccess`, per-field thresholds, and resource scopes. UI navigation states do not grant permissions.

Broker subscribers are trusted server-side code. A metadata-only event does not grant database access: use `Admin.read_event_record(event, principal)` or another explicitly authorized data retrieval path.

See [authentication](authentication.md), [authorization](authorization.md), [extensions](extensions.md), and [events](events.md).
