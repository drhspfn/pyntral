# Resources, fields, relationships, and navigation

[Documentation index](README.md) · [Python API](api-reference.md)

A `Resource` wraps a SQLAlchemy declarative model and controls how it appears in the admin. Model columns, primary keys, enums, nullability, and mapped relationships are introspected when registered.

## Register a resource

```python
from pyntral import Admin, Resource, Field, Relationship

admin.add_resource(Resource(
    User,
    name="users", label="Users", icon="users", navigation="People",
    navigation_order=10,
    visible_name=User.email,  # SQLAlchemy InstrumentedAttribute, checked for type
    list_fields=["id", "email", "active"],
    search_fields=["email"],
    page_size=25,
    show_search=False,
    form_layout="stack", detail_layout="stack",
    fields={
        "password_hash": Field(visible=False),
        "created_at": Field(readonly=True),
        "email": Field(label="Email address", filter_width=240),
    },
))
```

`Resource` can also be registered as a mapped model directly using `admin.add_resource(User)`, in which case defaults are inferred. `Resource.name` defaults to a pluralized, kebab-cased class name. Set it explicitly for irregular plurals.

### Resource configuration

| Argument | Effect |
| --- | --- |
| `model`, `name`, `label`, `icon` | ORM mapping and display identity. |
| `navigation`, `navigation_order` | Nested sidebar group path and ordering. |
| `list_fields`, `search_fields` | Columns shown in lists and used for text search. |
| `show_search` | Optional quick-search bar above advanced filters (off by default). |
| `fields` | Mapping of column names to `Field` overrides. |
| `visible_name` | Typed SQLAlchemy attribute used as a record label; supports string, integer, UUID columns. |
| `title_field` | Column-name alternative to `visible_name`. |
| `label_factory` | `(row) -> str` label callback for computed labels; does not automatically become SQL searchable. |
| `relationships` | Per-side mapped-relation presentation controls. |
| `form_layout`, `detail_layout` | `stack` (vertical) or `grid`. |
| `scope` | `(principal, statement) -> statement`; constrains database queries for that user. |
| `access` | Optional `RoleAccess` operation thresholds. |
| `allow_create/edit/delete/show` | Capability toggles. |
| `page_size` | Default page size, from 1 through 200. |
| `actions` | Record-level server callbacks and optional frontend views/dialogs. |

### Field configuration

`Field` supports `label`, `visible`, `readonly`, `required`, `widget`, `help`, `options`, `components`, `span`, `read_role`, `write_role`, `filter_operators`, and `filter_width`. `span` is `1` or `2`; `filter_width` must be an integer from 140 through 560 pixels. `components` maps a view (`list`, `edit`, `show`) to a registered TSX component ID.

`visible=False` removes a column from the admin’s default representation. **Use a separate serializer and strict authorization for genuinely sensitive data**—hiding a field is not a substitute for securing the underlying database or other application routes.

## Relationships

```python
admin.add_resource(Resource(
    Agent,
    relationships={
        "cover": Relationship(visible=False),
        "runs": Relationship(label="Recent runs", layout="table", selectable=True),
    },
))
admin.add_resource(Resource(
    FileAsset,
    relationships={"agents": Relationship(visible=False)},
))
```

Relationship presentation is configured **on each side independently**. This hides `FileAsset.agents` while retaining access to the `Agent.cover_id` column if it is otherwise allowed. `layout` supports `table` or `cards`; `selectable=True` adds selection controls to related lists. It does **not** automatically mutate foreign keys.

For a to-one foreign key, the editor and filter use the same server-backed select endpoint. Set `visible_name=Target.name` and `search_fields=["name"]` to control labels and search. When using `label_factory`, configure `search_fields` separately.

Deleting records with referenced rows can fail with HTTP 409. Pyntral deliberately does **not** invent cascade behavior: configure your ORM / FK schema, or implement application-level archival or soft deletion. See [troubleshooting](troubleshooting.md).

## Nested navigation and pages

```python
from pyntral import NavigationGroup, Page

admin.add_group(NavigationGroup("Agents", icon="bot", order=10))
admin.add_group(NavigationGroup("Agents/Operations", icon="cpu", order=20))

admin.add_resource(Resource(Agent, navigation="Agents"))
admin.add_page(Page(
    "insights", label="Insights", component="insights",
    navigation="Agents/Operations", icon="chart-column", min_role=None,
))
```

Pages are registered via Python and resolved to components in `pyntral.components.json`. They may share any nested group with resources. Use `Admin(show_dashboard=False)` to omit the standard dashboard.

## Custom record actions

An action handler receives the record, session, principal, and request payload (positional arguments). It can return a JSON-serializable result. Custom actions may commit business changes themselves; event delivery for actions does not imply a database commit.

```python
from pyntral import Action

def archive(record, session, principal, payload):
    record.active = False
    session.commit()
    return {"message": "Archived"}

resource = Resource(
    Customer,
    actions=[Action(
        name="archive", handler=archive, label="Archive", position="row",
        appearance="badge", confirmation="Archive this record?",
        visible=lambda principal, record: record.active,
    )],
)
```

`position` is `row`, `detail`, or `both`; `appearance` is `button`, `badge`, or `menu`. An `Action(component="profile")` opens a registered React action page; `Action(dialog="archive-dialog")` inserts a registered custom dialog body. `visible` may be a boolean or sync/async predicate. Pyntral checks access on the server, not just button visibility. See [extensions](extensions.md).

## Per-screen field configuration

`FieldView` configures each representation independently, without changing the
SQLAlchemy mapping. Global `Field(visible=False)` and role permissions continue to
win over per-view configuration.

```python
from pyntral import Field, FieldView, Resource

admin.add_resource(Resource(
    User,
    fields={
        "email": Field(
            list=FieldView(visible=True, order=1),
            show=FieldView(visible=True, order=2),
            create=FieldView(required=True),
            edit=FieldView(readonly=True),
            filter=FieldView(visible=True, operators=["eq", "contains"]),
        ),
        "internal_note": Field(
            list=FieldView(visible=False),
            show=FieldView(visible=False),
        ),
    },
))
```

For list/show responses, Pyntral excludes fields hidden in that context. Write
attempts to `readonly` edit fields and filters targeting hidden filter fields
are rejected by the server. `FieldView(component="component-id")` replaces
the field renderer for that context; `order` determines display order in
that context. `FieldView.required` augments validation for create/edit forms.

## Resource and bulk actions

`Action.kind` selects the execution scope. The default `record` kind keeps the
existing handler signature `(record, session, principal, payload)`. The other
kinds have explicit signatures:

```python
from pyntral import Action, Resource


def archive_selected(records, session, principal, payload):
    for record in records:
        record.active = False
    session.commit()
    return {"updated": len(records)}


def refresh_statistics(session, principal, payload):
    # Implement resource-wide work here. The framework does not execute
    # unbounded SQL updates automatically.
    return {"accepted": True}

admin.add_resource(Resource(User, actions=[
    Action("archive_selected", archive_selected, kind="bulk",
           confirmation="Archive the selected users?"),
    Action("refresh_stats", refresh_statistics, kind="resource"),
]))
```

`POST /admin/api/resources/users/actions/archive_selected` expects a JSON
object containing `ids` (1-100 distinct primary keys). All records must exist,
pass the resource's `scope`, record-level authorization and the action's
visibility predicate **before** the handler runs. The validated ORM instances
are passed in the given order. Resource actions use the same route without
`ids`. Handlers own their database commit and should be idempotent where needed.
The frontend provides a selection toolbar and corresponding action buttons.

## Editing SQLAlchemy many-to-many relationships

For a normal writable `relationship(secondary=...)`, the parent record view
provides an AsyncSelect picker, unlink action and optional create-and-link
form. The three corresponding POST endpoints are:

```text
/admin/api/resources/{parent}/{id}/relationships/{name}/attach
/admin/api/resources/{parent}/{id}/relationships/{name}/detach
/admin/api/resources/{parent}/{id}/relationships/{name}/create
```

`attach` and `detach` accept `{"id": 12}`. `create` accepts the new target
record's field data and commits the target + association together. `detach`
**never deletes the related record**. Every operation checks CSRF, parent edit
permission, target select permission and row scopes; create additionally
requires target create access. `viewonly` and non-secondary relations remain
read-only. Association tables requiring additional mandatory columns should
be handled by a custom action or an explicitly mapped association model.

## CRUD hooks

Use `Resource(hooks=[ResourceHook(...)])` for reusable lifecycle logic.
`before_create`, `before_update`, and `before_delete` run after authentication
and initial permission checks but before commit; hooks may reject an operation
with `AdminError`. A before-hook may edit `ctx.payload`, but Pyntral validates
all resulting keys again against the active principal's field permissions.
`after_*` hooks run after commit: failures are logged and do not undo the write.
Never use after-hooks for guaranteed delivery; use a transactional outbox for
that purpose.

```python
from pyntral import Resource, ResourceHook
from pyntral.orm import AdminError

def validate_stock(ctx):
    if ctx.payload.get("stock", 0) < 0:
        raise AdminError(422, "Stock cannot be negative", "validation_error")

admin.add_resource(Resource(Product, hooks=[ResourceHook(
    before_create=validate_stock, before_update=validate_stock,
)]))
```

## Virtual fields

`Resource.virtual_fields` registers values not mapped as SQLAlchemy columns.
A synchronous `getter(record)` can show a computed field in List/Show; a
sync/async `setter(record, value)` updates the model in the same CRUD transaction.
Use both callbacks for readable and writable virtual fields. Setter-only
fields never appear in list/show records; getter-only fields cannot be edited.
Virtual values are intentionally not SQL-filterable or sortable.

```python
from pyntral import VirtualField, Resource

admin.add_resource(Resource(Product, virtual_fields={
    "display_label": VirtualField(getter=lambda row: f"{row.name} / {row.sku}"),
    "rename_to": VirtualField(setter=lambda row, value: setattr(row, "name", str(value))),
}))
```

Configure `read_role` and `write_role` on virtual fields when access differs
from the resource. Virtual setters must not commit independently.

## Pydantic write validation

Specify `create_schema` and/or `edit_schema` with Pydantic `BaseModel` classes.
They validate values supplied in CRUD input (after permission checks and
before the ORM write). Other authorized model fields remain unchanged. Set
Pydantic optional fields for partial edit requests, or mark fields required
where appropriate. New fields added by a validator are not accepted.

```python
class ProductPriceRules(BaseModel):
    price: Decimal | None = None

    @field_validator("price")
    @classmethod
    def check_price(cls, price):
        if price is not None and price <= 0:
            raise ValueError("Price must be positive")
        return price

admin.add_resource(Resource(Product,
    create_schema=ProductPriceRules, edit_schema=ProductPriceRules))
```

Pyntral returns 422 with affected field names, deliberately omitting raw
input and validator exception text to avoid exposing secrets in responses.

Validation in Pyntral is opt-in per resource, not inferred automatically from
`SQLAlchemy.String(240)` or a unique index. The Shop Customer demonstration
uses `CustomerCreateRules` and `CustomerEditRules` to reject malformed email
addresses, blank names and invalid edits with HTTP 422; duplicate addresses
remain a database uniqueness violation (HTTP 409). The email field also uses
`Field(widget="email")` for native browser feedback.

## Optimistic concurrency

Opt in with `Resource(..., version_field="version")` and a SQLAlchemy integer
column mapped as `__mapper_args__ = {"version_id_col": version}`. Pyntral
validates this configuration at registration. PATCH and DELETE require an
`If-Match: <version>` header; missing headers get 428, stale versions get 412.
SQLAlchemy's versioned UPDATE/DELETE rejects a concurrent commit with 409.
The bundled React editor automatically sends the version it originally loaded.
Do not implement version checks using an unguarded integer read/compare alone.

## Layout sections

Declare `form_sections` and `detail_sections` as `LayoutSection` instances.
Kinds: `section`, `tab`, `accordion`. Fields may appear in at most one declared
section per view, with remaining visible fields shown in a fallback section.
`visible_if={"field":"active", "equals":True}` hides a group **in the UI
only**; it never grants or removes access to its fields. All values and
permissions are validated server-side as usual.

```python
from pyntral import LayoutSection

Resource(Article, form_sections=[
    LayoutSection("general", "General", ["title"], kind="tab"),
    LayoutSection("content", "Content", ["body"], kind="tab"),
], detail_sections=[
    LayoutSection("summary", "Summary", ["title", "version"]),
    LayoutSection("body", "Body", ["body"], kind="accordion"),
])
```

## Composable resource features

A feature implements `apply(resource)` and may register virtual fields,
configuration, actions and CRUD hooks. Features are applied before ORM
introspection, once for a given resource object. A registration conflict
raises an error rather than silently replacing an existing field/action.

`PasswordFeature` creates a write-only `new_password` input and hashes into a
hidden SQLAlchemy `password_hash` column. `SoftDeleteFeature` adds Archive and
Restore record actions on a nullable `deleted_at` column and disables hard
delete by default. The latter **does not globally hide archived records**;
resource-level scopes should be configured if needed.

```python
from pyntral import PasswordFeature, SoftDeleteFeature
Resource(StaffAccount, features=[PasswordFeature(), SoftDeleteFeature()])
```

The Shop Demo has **Security → Demo staff**, a live example. These records are
not connected to the Shop authentication backend.

## Server-managed timestamps

`TimestampFeature(created_field="created_at", updated_field="updated_at")`
adds both timestamps during creation and advances only `updated_at` on
subsequent edits. Both mapped columns are read-only in Pyntral and the values
are produced inside the ORM transaction, rather than trusting the browser.
Model columns must exist and be nullable or accept timezone-aware UTC datetimes.

## Transactional AuditFeature

`AuditFeature()` creates one `pyntral_audit_entries` row per normal CRUD
mutation using the same SQLAlchemy transaction. Rows contain operation,
resource/record/actor identifiers and **field names only**, not values.
Create the table with `AuditBase.metadata.create_all(engine)` during local
demo setup; production projects should use an Alembic migration instead.
Register `Resource(AuditEntry, allow_create=False, allow_edit=False,
allow_delete=False)` to inspect the audit trail from a secured admin view.
Arbitrary custom Actions and M:N operations are not part of this CRUD hook.

## Secure resource uploads

Enable `UploadFeature(max_bytes=...)` for selected resources and provide
`Admin(storage=LocalStorage(Path("private-uploads")))`. Files are stored by
server-generated opaque keys and indexed in `UploadEntry`. Create the
`pyntral_uploads` table through `UploadBase.metadata` in local development or
Alembic in production. Authenticated routes enforce owner record scopes:

- `GET /admin/api/resources/{resource}/{id}/uploads` — metadata list
- `POST /admin/api/resources/{resource}/{id}/uploads` — raw binary body plus
  `X-Filename` header, CSRF, size limit and owner edit permission
- `GET /admin/api/uploads/{upload_id}` — authorized attachment download
- `DELETE /admin/api/uploads/{upload_id}` — authorized deletion

Downloads force `Content-Disposition: attachment`, preventing accidental inline
HTML execution. An S3/MinIO-compatible adapter is available with
`pyntral[s3]`:

```python
from pyntral import UploadFeature, LocalStorage, S3Storage
storage = S3Storage(bucket="private-admin-assets", endpoint_url="https://minio.example.org")
admin = Admin(app, storage=storage, ...)  # all other constructor arguments required
admin.add_resource(Resource(Article, features=[UploadFeature(max_bytes=5_000_000)]))
```

S3 credentials come from boto3's standard environment/credentials chain;
never embed them in frontend JSON schemas. A file deletion is not a transaction
across the object store and SQL database; applications requiring coordinated
cleanup should use a durable outbox.

## Offline schema reference generation

Use `pyntral schema module:app --out .pyntral/schema.md` (or `--format json`) to
create a value-free developer reference from the same resource registry used
by the application. No Vite, Node.js or browser process is needed. This static
file is **not** a user-scoped authorization view: do not publish it to untrusted
parties if your model names or field metadata are confidential. Hidden mapped
fields are excluded. See [the Shop example](../examples/shop/README.md).

## Server-driven dependent selects

`Field(dependency=FieldDependency(source="country", bridge="shipping-city-options"))`
requests options from a named, authorized Pydantic Bridge when the source field
changes. The input is `{ "country": "..." }` and the Bridge output model must
contain an `options` array with `{ "label": str, "value": str | int }` entries.
Do not rely on the option list as a permission check: validate the final selection
server-side using Pydantic or a `ResourceHook`. Both the bridge and the resource
mutation enforce their own authentication and permissions. The Shop's Shipping
locations resource illustrates this behavior.

## Async resource jobs (in-process only)

Define `JobAction(name, async_handler, timeout_seconds=300)` in `Resource(jobs=[...])`.
The handler receives `JobContext(principal, payload, session_factory)` and may
call `ctx.progress(percent, message)` while it runs. `POST` to
`/admin/api/resources/{name}/jobs/{job_name}` returns an opaque job ID; the
initiating principal may poll `GET /admin/api/jobs/{id}` or request cancellation
with `DELETE /admin/api/jobs/{id}`. These routes require sessions, CSRF on
writes, and resource-action permissions. Requests are bounded, jobs time out,
completed entries expire, and tasks are cancelled during FastAPI shutdown.
**Jobs are not persisted or transferred between workers.** Use a real broker
and durable worker for long-running, must-not-lose tasks.

## Custom action hooks

`ResourceHook(before_action=callback, after_action=callback)` also wraps record,
bulk and resource actions. `OperationContext.action` identifies the action,
`record` contains a checked record for record actions, and `records` contains
pre-authorized ORM instances for bulk actions. A before-hook can validate or
modify the action payload; throwing an `AdminError` blocks the handler. After
hooks run only after successful handlers and are logged if they fail, but they
do not imply an ORM commit. See the Shop Orders Fulfill action.

## Declarative FileUpload mock field

Use `Field(file_upload=FileUploadConfig(...))` on a mapped **JSON column** to expose a mock-only file picker in built-in Create/Edit screens:

```python
from pyntral import Field, FileUploadConfig, Resource

Resource(MyAssetDraft, fields={
    "attachments": Field(label="Attachments", file_upload=FileUploadConfig(
        multiple=True, max_files=4, max_size_bytes=2_000_000,
        max_total_bytes=6_000_000, accept="image/png,image/jpeg,application/pdf",
        preview=True, allow_paste=True,
    )),
})
```

This first version is explicitly mock-only: the browser holds native `File` objects, and selecting files cannot result in a CRUD save containing fake file objects. Saving a record with staged mock files raises a user-visible error until the selections are cleared. No file bytes, object URLs, signed upload grants or file receipts travel through the resource schema or generic JSON `POST/PATCH`. Existing `UploadFeature` endpoints remain separate and unchanged. Actual S3/MinIO persistence needs an authenticated initiation/verification/finalization protocol and must not infer a trusted MIME type or checksum solely from the browser.
