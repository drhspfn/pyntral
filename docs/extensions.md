# Custom React extensions

[Documentation index](README.md) · [UI components](ui.md) · [Bridges](bridges.md)

The published Pyntral Python wheel contains a complete generic SPA that works without a frontend toolchain. For optional custom UI, Pyntral compiles developer-supplied TSX components into an application-specific administration SPA. Python configuration references an extension by ID; `pyntral.components.json` maps that ID to a local file relative to the project root.

## Registry configuration

```json
{
  "app": "examples.shop.app:app",
  "fields": { "asset-image": "admin/AssetImage.tsx" },
  "pages": { "insights": "admin/Insights.tsx" },
  "actions": { "customer-profile": "admin/CustomerProfile.tsx" },
  "dialogs": { "archive-notice": "admin/ArchiveNotice.tsx" },
  "themes": {},
  "crud": { "resource-summary": "admin/ResourceSummary.tsx" },
  "profile": {},
  "access": {},
  "auth": {}
}
```

The config file is optional, but must use valid relative paths beneath the project root. Vite refuses extensions outside that root. Run `pyntral init-ui` to scaffold an example field and configuration, or write TSX files directly.

## Custom list/show/edit field

```python
from pyntral import Field, Resource

admin.add_resource(Resource(
    Agent,
    fields={"cover_id": Field(components={
        "list": "asset-image", "show": "asset-image",
    })},
))
```

```tsx
import type { CustomFieldProps } from "@pyntral/types";

export default function Cover({ value, record, mode }: CustomFieldProps) {
  if (!value) return <span>No cover</span>;
  return <span title={`Agent ${record.id}`}>Asset {String(value)} ({mode})</span>;
}
```

`CustomFieldProps`: `field`, `value`, `record`, `resource`, `mode` (`list`, `edit`, `show`, `filter`) and optional `onChange`. For dynamic data, call a Pydantic bridge as demonstrated in [`AssetImage.tsx`](../admin/AssetImage.tsx).

## Pages, record actions, and dialogs

```python
from pyntral import Action, Page

admin.add_page(Page("insights", "Insights", component="insights", navigation="Agents"))
resource.actions.append(Action(
    "archive", archive_customer,
    label="Archive", appearance="badge", position="both",
    dialog="archive-notice",
))
```

`CustomPageProps` receives `{ schema, navigate }`. `CustomActionProps` receives `{ schema, resource, record, action, navigate, invoke }`; `invoke(payload?)` calls the registered backend action. `ActionDialogProps` gets `{ resource, record, action }` to render contents inside a confirmation dialog. A custom action may instead specify `component="customer-profile"` to show a dedicated page.

Backend actions still require their own access checks and do not automatically commit arbitrary changes. Use the global `useAdminFeedback()` and the API/mutation helpers from the registered frontend environment for toasts, confirmation, and cache updates.

## Profile menu, access denied, login, and theme extensions

Extension categories and their React props:

| Category | Props | Purpose |
| --- | --- | --- |
| `profile` | `{ user, schema, navigate, close }` | Additional user-menu entries alongside the built-in sign out. |
| `access` | `{ resource, currentAdmin }` | Access-denied UI. The server still returns 403. |
| `auth` | `{ onAuthenticated, config, themeMode, toggleTheme }` | Custom login screen; should call verified server authentication endpoints. |
| `themes` | `{ schema, mode }` | Theme-level React decoration/customization. |

Use `@pyntral/types` for the corresponding types. A custom login screen does not make unverified IdP tokens trustworthy: see [authentication](authentication.md).

## Build and source tracking

```bash
uv run pyntral types examples.shop.app:app
uv run pyntral dev examples.shop.app:app
uv run pyntral build --app examples.shop.app:app
```

The CLI hashes the component config and referenced TSX files. `dev` uses Vite HMR; `build` compiles TypeScript and writes `.pyntral/dist/`. Modifying a Python resource's metadata alone does not require a JS build; changing extension source code does.

For full frontend props, inspect [`src/pyntral/ui/src/types.ts`](../src/pyntral/ui/src/types.ts) and [`ui.tsx`](../src/pyntral/ui/src/ui.tsx): these are the authoritative TypeScript contracts for this beta.

## Replacing complete CRUD screens

Register an optional `crud` entry in `pyntral.components.json` and assign it
to a resource through `crud_views`. This replaces an entire default
`list`, `create`, `edit` or `show` screen while preserving the existing secured
REST API and server-side permissions.

```json
{
  "crud": {"people-list": "admin/PeopleList.tsx"}
}
```

```python
admin.add_resource(Resource(Person, crud_views={"list": "people-list"}))
```

A TSX component receives `CustomCrudProps` from `@pyntral/types`, including
`mode`, `schema`, `resource`, optional `record`, `navigate`, `loadList(params)`,
`save(data)`, `remove()`, `reload()` and `defaultView`. Helpers use the authenticated, CSRF-
protected Pyntral API; custom pages do not bypass resource permissions.
`remove()` presents the standard destructive confirmation. You may use any
available Pyntral UI primitive or React component inside the override.

For resource/bulk action pages, register an action component as usual. It
receives `CustomCollectionActionProps`, with `selectedIds` and `invoke(payload)`;
all IDs are revalidated by the backend on invocation.

## Sidebar extensions

Use declarative `SidebarConfig` for standard branding. To replace or augment regions, register these optional extension IDs in the manifest:

```json
{
  "sidebarHeaders": { "shop-header": "admin/SidebarRegion.tsx" },
  "sidebarFooters": { "shop-footer": "admin/SidebarRegion.tsx" },
  "sidebarItems": { "shop-item": "admin/SidebarItem.tsx" }
}
```

```python
sidebar = SidebarConfig(
    header_component="shop-header",
    footer_component="shop-footer",
    item_component="shop-item",
)
# Pass sidebar=sidebar to Admin(...)
```

Header and footer components receive `SidebarRegionProps`: `schema`, `config`, `user`, `themeMode`, `navigate(route)`, `close()`, and `children` containing the default region (or null). They can render their own layout or wrap the existing content. Navigate through the supplied callback to retain router guards and mobile drawer behavior.

Item extensions receive `SidebarItemProps`: `type`, `id`, `label`, `icon`, `depth`, `active`, `locked`, `open` (groups only), `schema`, and `children` containing the built-in item content. The framework owns the outer button, accessible label, navigation, group disclosure and access-denied behavior. Render only non-interactive content inside item extensions (no nested buttons or links).

```tsx
import type { SidebarItemProps } from "@pyntral/types";

export default function MyItem({ children, active }: SidebarItemProps) {
  return <>{children}{active && <small aria-hidden="true">•</small>}</>;
}
```

These slots participate in the existing custom build, manifest fingerprinting, editor type generation and extension linting. Missing registry IDs fall back to the default UI.

### Custom login screen presentation

The existing `auth.login` component receives `LoginScreenProps` with
`onAuthenticated`, `config` (PublicLoginConfig), `themeMode`, and
`toggleTheme`. Existing implementations that only consume
`onAuthenticated` continue to work. The global theme tokens are installed
before the extension renders.

```tsx
import type { LoginScreenProps } from "@pyntral/types";
import { Brand, Button } from "@pyntral/ui";

export default function CustomLogin({ config, themeMode, toggleTheme }: LoginScreenProps) {
  return <main>
    {config.login.brand && <Brand config={config.login.brand} themeMode={themeMode}/>}
    <Button onClick={toggleTheme}>Toggle theme</Button>
    {/* Add your actual credential/verified-token flow here; call onAuthenticated only with the server response. */}
  </main>;
}
```

## Compose standard CRUD views

Register component IDs in the existing `crud` manifest category. Add before
and after slots without rebuilding the default list, table, or record editor:

```python
Resource(Usage, crud_slots={"list": {"before": "resource-summary"},
                            "show": {"after": "resource-summary"}})
```

Slot components receive `CustomCrudProps` (including the authorized record
on record routes). They render around the standard screen or a configured
replacement. A full `crud_views` override can alternatively render
`props.defaultView` once inside its own wrapper. Slots must not render that
element again. Standard controls retain their own queries, mutations and
pagination. The API remains subject to normal access checks.

```tsx
import type { CustomCrudProps } from "@pyntral/types";
import { Card } from "@pyntral/ui";

export default function Metrics({ resource }: CustomCrudProps) {
  return <Card title={resource.label}>Additional resource information</Card>;
}
```

A full CRUD override can also wrap the default view:

```tsx
import type { CustomCrudProps } from "@pyntral/types";
import { Card } from "@pyntral/ui";
export default function WrappedDetail({ defaultView }: CustomCrudProps) {
  return <><Card title="Additional context">Original controls stay intact.</Card>{defaultView}</>;
}
```

Slots accept all four modes and both positions, one extension per position.
They render around the complete screen, not inside the toolbar. Record routes
receive the authorized record once loaded. Save is available for create/edit;
render the default view only once in an override. See the working
[ResourceSummary](../admin/ResourceSummary.tsx) example.

## HTTP client: @pyntral/api

Use the public `api<T>(path, options)` for JSON requests that do not need a
generated bridge. Admin-relative paths start with `/` and resolve below the
configured ASGI mount (including a reverse-proxy prefix). The client includes
same-origin cookies, attaches the current admin CSRF token to non-safe admin
requests, and raises `ApiError` with status, code, message and details.

```tsx
import { api, buildQuery } from "@pyntral/api";
const rows = await api<{ items: Record<string, unknown>[] }>(
  "/api/resources/orders" + buildQuery({ limit: 10 })
);
// Register this application-owned admin route on the backend first:
const result = await api<{ ok: boolean }>("/api/custom-operation", {
  method: "POST", body: JSON.stringify({ id: 42 })
});
```

To address a host FastAPI route outside the admin mount, pass
`{ scope: "host" }`, e.g. `api("/health", { scope: "host" })`. It uses
the current origin and its cookies but does not forward the admin CSRF
token automatically. Host routes own their authentication, CSRF and
authorization policies. In Vite development they also need an appropriate
proxy or same-origin server route; the default proxy only forwards the
admin API/auth prefixes. Use `fetch` for non-JSON responses. FormData and
binary bodies are supported without forcing the JSON content type.

`ApiOptions` extends RequestInit with `scope?: "admin" | "host"`. The generic
result type is compile-time only, not runtime validation. Use generated bridges
for Pydantic DTO validation. `base` exposes the mount; `buildQuery` encodes query
parameters. See [Insights](../admin/Insights.tsx) for a live admin HTTP call.
