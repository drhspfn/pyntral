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

### Optimistic concurrency

**Commerce → Editorial Drafts:** Open the same draft in two browser tabs, save
in the first, then attempt to save the stale second tab. The second write
receives HTTP 412 instead of silently overwriting another administrator's
changes. Refresh the second tab to retrieve the latest version. The model
uses SQLAlchemy `version_id_col` for an atomic optimistic version check.
