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
| `auth` | `{ onAuthenticated }` | Custom login screen; should call verified server authentication endpoints. |
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
