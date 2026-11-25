# Authorization and permissions

[Documentation index](README.md) · [Authentication](authentication.md)

Pyntral supports two complementary authorization layers: role thresholds (`RoleAccess`) and the `AuthBackend.authorize(principal, resource, action, record)` callback. A resource may also apply a SQLAlchemy query `scope` to enforce row-level visibility.

## Role thresholds

```python
from pyntral import Admin, Resource, RoleAccess, Field

admin = Admin(
    app, session_factory=SessionLocal, auth=auth, secret_key=secret,
    role_weights={"viewer": 10, "avatar-manager": 20, "voice-editor": 30, "admin": 100},
)
admin.add_resource(Resource(
    Avatar,
    access=RoleAccess(read="viewer", write="avatar-manager"),
))
admin.add_resource(Resource(
    Voice,
    access=RoleAccess(read="avatar-manager", select="avatar-manager", write="voice-editor", navigation="lock"),
))
```

An avatar manager can read/select a Voice for an Avatar relationship, but cannot change the Voice record. Selection permission does not imply write permission. The server checks that foreign key assignments reference records the principal can select.

`RoleAccess` accepts `read`, `select`, `write`, `create`, `edit`, `delete`, and `navigation`. `select` defaults to `read`. `create`, `edit`, and `delete` default to `write`. A custom action requires `write` plus callback authorization. Unknown roles fail closed. **Omitting `write` denies writes**, and role-based mutation permissions also require read access.

If you specify `RoleAccess`, define explicit role thresholds. A resource without `RoleAccess` remains governed by its flags and the auth backend; the built-in callback backend's default `authorize` allows actions unless overridden. Define an explicit policy for public deployments.

## Per-field protection

```python
Resource(
    User,
    fields={
        "email": Field(read_role="viewer", write_role="admin"),
        "password_hash": Field(visible=False),
    },
)
```

Pyntral filters response fields and edits according to the role thresholds. Foreign-key fields can also be omitted when the target resource is not accessible. Do not rely on a hidden field or sidebar alone to secure other application endpoints.

## Per-record callbacks and scopes

```python
async def authorize(principal, resource, action, record=None):
    if resource == "users" and action == "delete":
        return "admin" in principal.roles
    return True

# Restrict list/get/relations at query level (statement -> statement):
def scope(principal, stmt):
    return stmt.where(User.organization_id == principal.attributes["organization_id"])

Resource(User, scope=scope)
```

Scopes must be applied consistently in the application's other data-access routes too. For external IdPs, derive organization membership server-side and re-check it during requests.

## Sidebar state

`navigation="hide"` hides inaccessible resources; `navigation="lock"` may show disabled entries and an access-denied dialog. Neither setting grants direct route/API access. `Page.min_role` and `Bridge.min_role` provide separate minimum thresholds for custom pages and bridge endpoints.

## Access matrix

| Operation | Server responsibility |
| --- | --- |
| List / Show | Resolve principal, require read permission, apply scope and field filtering. |
| Select related row | Require select permission for target, respect target scope. |
| Create / Edit | Require operation permission, validate fields and foreign keys, check CSRF. |
| Delete | Require delete permission; DB constraints remain authoritative. |
| Custom Action | Require write/action authorization and evaluate `visible` predicate. |
| Bridge | Require authenticated principal and optional `min_role`. |

For full threat-model guidance, consult [SECURITY.md](../SECURITY.md).

## Contextual resource and field policies

A resource can further restrict operations using `operation_policy(principal,
action, record) -> bool`, which can be sync or async. `record` is `None`
for collection-level permissions and is an ORM instance for record actions.
`False` denies the operation on the server, regardless of UI visibility.

Fields can independently use `Field(read_when=..., write_when=...)`. Both
predicates receive `(principal, record)` and may be sync or async. The
field is redacted from each unauthorized record in list/show responses and
write attempts return HTTP 403. A field with conditional read permission
cannot be used in sorting, text search or advanced filters (even by probing
query parameters) because those operations could reveal hidden data. This
also applies to exports, searches of related records, and option searches.
Option lookups and foreign-key writes enforce the target row's `select`
policy. Options fall back to a readable primary key when their title field
is unavailable. Custom label callbacks run only when the row's declared
role-protected and conditional fields are readable. Keep callback output
limited to data intended for the selector. Use `Resource.scope` to enforce
database-level row isolation.

## Dashboard authorization

Home and category dashboards are authenticated UI extensions, not independent
REST endpoints. The schema includes Admin.dashboard_component only if
the home dashboard is enabled and the auth callback permits
`("dashboard:<component-id>", "view")`. A denied home extension falls
back to the ordinary Overview. A category landing page requires
`("group:<full/path>", "view")` and its optional NavigationGroup.min_role
threshold (configured in Admin.role_weights). Its component ID is omitted
when denied; authorized descendants keep their normal navigation entries.

```python
async def authorize(principal, resource, action, record=None):
    if action == "view" and resource.startswith(("dashboard:", "group:")):
        return "admin" in principal.roles
    # Apply the application's existing resource/page policies here.
    return True
```

Sidebar search only filters the authenticated schema, including intentionally
locked entries; it grants no additional access. A dashboard receives the
signed-in principal and scoped schema, but must still use authorized resource
or bridge requests for data. JavaScript bundles are not access-control
boundaries: never embed private data, credentials or secrets in TSX.
See [dashboard configuration](extensions.md#home-and-category-dashboards).
