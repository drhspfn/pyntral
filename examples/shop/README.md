# Shop demo — production Docker smoke test

This example builds the Pyntral React SPA and the custom components into static
assets, then serves them from FastAPI/Uvicorn without Node.js in the final image.

Run these commands **from the repository root**:

```powershell
uv run pyntral init-env  # only once; creates your local .env
# Compose 2.30+ is required for env_file: format: raw
# Password hashes contain '$' and must not be interpolated.
docker compose -f examples/shop/compose.yaml build --progress=plain
docker compose -f examples/shop/compose.yaml up -d
docker compose -f examples/shop/compose.yaml ps
docker compose -f examples/shop/compose.yaml logs -f shop
```

Open <http://127.0.0.1:8000/admin/> and sign in with the account from `.env`.
Direct navigation to `/admin/resources/products` followed by a browser refresh
must load the SPA; the `/health` endpoint should return `{"status":"ok"}`.

The Docker build runs the same strict TypeScript check as `pyntral build`.
Errors indicate a failed build, not a successful production bundle.

The root `.dockerignore` and `examples/shop/Dockerfile.dockerignore` prevent
secrets, SQLite databases, Git data, local virtualenvs and generated caches from
being copied into the Docker build context.

The `.env` file is read only by Compose **at runtime**, not by the image builder.
Do not expose this local HTTP deployment publicly: cookies are intentionally
not marked Secure for this example. Run behind HTTPS and enable secure cookies
for actual deployments.

Stop and remove:

```powershell
docker compose -f examples/shop/compose.yaml down
# To discard the seeded SQLite data as well:
docker compose -f examples/shop/compose.yaml down -v
```

## Interactive feature showcase (latest API)

The Shop example demonstrates Pyntral features using real SQLAlchemy models,
not mock endpoints. From the repository root, start the development UI:

```bash
uv sync --extra dev
uv run pyntral init-env  # only if you do not already have .env
uv run pyntral dev examples.shop.app:app
```

Open <http://127.0.0.1:5173/admin/>. The sample database is seeded once on
startup; existing customer, product and order data is preserved. New Tags and
product-tag associations are added independently when upgrading an existing
`shop.db` that has not yet been tagged.

| Feature | Where to try it | Expected behavior |
| --- | --- | --- |
| Per-view `FieldView` | **Commerce → Customers** | Email is absent from the list, visible on Show, readonly on Edit, and filterable with Equals/Contains; name is required on Create. |
| Record actions | **Customers → a customer** | Existing Archive and Profile actions remain available. |
| Bulk action | **Customers → select at least one row → Archive selected** | The selected customers become inactive after confirmation. No rows are deleted. |
| Resource action | **Customers → Reactivate all** | After confirmation, all inactive customers become active again. |
| Custom CRUD screen | **Commerce → Tags** | A custom `admin/TagCatalog.tsx` React list renders colored tag cards. Click a tag for the normal Show page or **New tag** for the generated Create form. |
| Editable many-to-many | **Commerce → Products → a product → Product tags** | Search/link existing tags, unlink without deleting them, or create-and-link a new tag. The linked tags remain available as regular records. |
| Other extensions | **Agents / Insights / Orders** | Existing custom Image field, custom page, badge, record actions and bridge continue to work. |

The matching registration lives in `examples/shop/app.py`, the custom CRUD
component lives in `admin/TagCatalog.tsx`, and `pyntral.components.json` maps
its extension ID. For a standalone regression check, run:

```bash
uv run pytest -v tests/test_shop_feature_demo.py
uv run pytest -v tests/test_view_actions_relations.py
```

Do not copy this demo's unscoped resource-wide Reactivate action directly into
a multi-tenant application: production handlers should explicitly enforce
tenant and row scopes as well as Pyntral authorization.

### CRUD lifecycle hooks

**Commerce → Products:** Try creating a product with `Stock = -1`, or editing
an existing product to a negative stock. The request is rejected with HTTP 422
and the database remains unchanged. The example uses `ResourceHook` for both
`before_create` and `before_update`.

### Computed and write-only fields

**Commerce → Products:** The `Name / SKU` column is a computed virtual field:
it is not stored in the SQL table and cannot be sorted or filtered in SQL.
**Edit product → Rename product** changes the mapped name through a write-only
virtual setter. The submitted value is never serialized into API responses.

### Pydantic write validation

**Commerce → Products:** Enter a price of `0` or a negative amount when
creating/editing a product. `ProductPriceRules` rejects it with a field-level
validation error before SQLAlchemy commits. Validators receive only authorized
fields, and raw input is excluded from error payloads.

### Customer field validation

**Commerce → Customers → New record:** Email uses the browser's email input
type for immediate feedback, and `CustomerCreateRules` checks email shape
on the Python backend. Submitting `123`, an address without a domain, a blank
name, or a name shorter than two characters returns HTTP 422 without creating
a row. Leading/trailing whitespace in a valid name is stripped.

The existing database uniqueness constraint still rejects duplicate emails
with HTTP 409. On Edit, `CustomerEditRules` validates changed names, while the
email field remains read-only. The frontend input is a convenience, not the
security boundary. The demo regex targets common email addresses, not every
RFC-valid address; applications requiring full email standards support can use
Pydantic's `EmailStr` with the `email-validator` dependency.

### Optimistic concurrency

**Commerce → Editorial Drafts:** Open the same draft in two browser tabs, save
in the first, then attempt to save the stale second tab. The second write
receives HTTP 412 instead of silently overwriting another administrator's
changes. Refresh the second tab to retrieve the latest version. The model
uses SQLAlchemy `version_id_col` for an atomic optimistic version check.

### Declarative layout sections

**Commerce → Editorial Drafts → Create/Edit:** The editor uses Overview/Content
*tab* sections without requiring custom React. **Show** renders Summary as a
section and Full content as an accordion. Non-declared fields still render in
an "Other details" fallback, so adding a model column does not hide it.

### Composable features

**Security → Demo staff:** Create a demo staff record with a username and a
password. `PasswordFeature` hashes the password into the hidden column; the
write-only input and resulting hash never appear in list/show responses.
On the record page use Archive, then Restore to exercise `SoftDeleteFeature`.
Hard deletion is disabled. These are demonstration accounts, not identities
used by the Shop login backend.

### Server-managed timestamps

**Commerce → Editorial Drafts:** Create a draft, then edit its content. The
`created_at` timestamp remains unchanged while `updated_at` advances. Both
fields are managed by `TimestampFeature` and cannot be written via JSON input.
Existing local SQLite databases are migrated without dropping user records.

### Transactional audit trail

**Commerce → Editorial Drafts:** Create or edit a draft, then open **Security →
Audit entries** to see an audit row containing the resource name, record ID,
administrator ID, operation and changed field names. No previous/new values
are stored. Audit rows are inserted in the same database transaction as the
normal mapped CRUD operation. Actions and M:N mutations have separate
semantics and are not automatically audited by this feature.

### Authenticated attachments (Local/S3/MinIO)

**Commerce → Editorial Drafts → a draft → Attachments:** Select a file and
upload it; download via the protected API link or delete it. Users without
write permission cannot upload/delete. The Shop uses `LocalStorage` under
`.pyntral/uploads/` by default and enforces a 2 MB request limit. This is a
private demonstration directory: do not put it under a public static server.
`S3Storage(bucket=..., endpoint_url=...)` uses the same API with AWS S3 or
MinIO (requires `pyntral[s3]`). For persistence in Docker, mount a volume for
`SHOP_UPLOAD_ROOT`.

### Table preferences and saved filter presets

**Commerce → Products → Columns:** Hide/reorder columns, pin one column, or
switch between Comfortable and Compact row density. Open Filters, set a price
range, type a preset name, and press Save preset. Change filters, then restore
the saved preset from the menu. Preferences are stored in this browser for the
current administrator ID and resource, never used as an authorization rule.
Bulk selections remain available when moving between pages of the same query.

### Localization

Restart Shop with `SHOP_LOCALE=ru` in the environment to see Russian labels
for key navigation, toolbar, CRUD and table actions; dates follow the resolved
language. The default is English. Host applications may provide their own
language dictionaries and per-principal locale resolver. Model field labels
and resource names remain independently configurable in Python.

### Per-admin theme preferences

The server selects `light`/`dark` preferences and accent tokens using
`theme_resolver(principal)`. For this example the administrator receives a
dark-mode accent; the function may also read persisted user preferences.
`Admin(theme={...})` remains the global fallback, and only the verified
principal influences the server-provided defaults. Users can still toggle
their local theme from the header.

### Conditional authorization

Create an **Editorial Draft** with a title beginning `[Locked]` to test the
per-record `operation_policy` (hard delete is denied) and the `body` field's
`Field.write_when` rule (editing the body is denied with HTTP 403). Other
fields remain editable; restrictions are checked on the server. Separate
`Field.read_when` conditions can redact data on a per-row basis, including
in related lists; such fields cannot be sorted or filtered to avoid leaks.

### Generate a resource API reference without Node.js

From the repository root, run:

```bash
uv run pyntral schema examples.shop.app:app --out .pyntral/shop-schema.md
uv run pyntral schema examples.shop.app:app --format json --out .pyntral/shop-schema.json
```

The generated documents list the registered resources, view-visible fields,
relationships, action scopes and bridge names. They never include sample record
values or password hashes. These developer-only documents are **not** served
as an unauthenticated HTTP route; permissions remain enforced at runtime.

### Dependent field options with Pydantic Bridge

**Commerce → Shipping → Shipping locations → Create:** Choose a country, then
open the City picker. The available cities come from the authenticated
`shipping-city-options` Bridge and change when you choose another country.
The previous city selection is cleared automatically. Sending an incompatible
country/city combination to the REST API is rejected with HTTP 422 by a
Python `ResourceHook`, independent of the React UI.

### Optional realtime invalidation

Open **Commerce → Products** in two logged-in browser tabs. Edit a product in
one tab; the other tab's active table/record queries are invalidated through
an authenticated SSE connection and refetched without a manual refresh. The
stream carries only a generic invalidation signal — no resource names, record
IDs or values. The Shop enables `Admin(realtime_updates=True)`; production
applications can leave it disabled. Delivery is best effort, and multi-worker
broadcast requires an appropriate broker topology (not a shared competing
consumer queue).

### Background resource actions with progress and cancellation

**Commerce → Products → Rebuild inventory report:** The button launches a
bounded in-process async job, displays progress and supports cancellation.
The job explicitly creates a new SQLAlchemy session if needed; it never retains
request-scoped sessions. This demo does not change inventory data. Job status
is visible only to the administrator who launched it. It is intentionally not
a durable queue — production jobs requiring crash recovery must use a worker
system (RabbitMQ, Redis Streams, etc.) rather than this convenience feature.

### Hooks around custom Actions

**Commerce → Orders → an order → Fulfill:** The order's `before_action`
hook rejects cancelled orders with HTTP 422 before the custom action handler
runs. `ResourceHook.before_action` and `after_action` also cover resource-wide
and bulk actions. Hooks never bypass the normal server-side action permissions;
handlers are responsible for their own database commits.
