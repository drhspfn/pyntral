# Authentication and current administrator

[Documentation index](README.md) · [Authorization](authorization.md)

An `Admin` requires an `AuthBackend` and a `secret_key` of at least 32 characters. It mounts signed-cookie sessions with a CSRF token for state-changing requests. `secure_cookie=True` is the production default: serve Pyntral behind HTTPS.

## Local credentials

Use this for demos and private single-admin environments:

```bash
uv run pyntral hash-password
# Set ADMIN_USERNAME and ADMIN_PASSWORD_HASH securely
```

```python
from pyntral import LocalAuth

auth = LocalAuth.from_env()   # ADMIN_USERNAME / ADMIN_PASSWORD_HASH
# or LocalAuth(username="admin", password_hash=stored_hash, roles=["admin"])
```

`pyntral init-env` interactively creates a local `.env` with a password hash and an app secret for the demo. Do not use a hard-coded example password in production.

## Database-backed accounts

```python
from pyntral import ModelAuth

auth = ModelAuth(
    session_factory=SessionLocal,
    model=AdminUser,
    username_field="email",
    password_field="password_hash",
    active_field="active",
    roles_field="role",
)
```

The backend uses the model’s primary key as the identity and reloads it through `resolve` for subsequent requests. Password hashes use the library's scrypt format; migrate existing hash schemes through your own callback if necessary. `roles_field` may be a scalar or list-like value.

## Custom callbacks and verified external tokens

```python
from pyntral import CallbackAuth, Principal

async def login(username: str, password: str) -> Principal | None:
    # Verify credentials in your own identity service.
    ...

async def resolve(principal: Principal) -> Principal | None:
    # Reload account status; return None to revoke access.
    return principal

async def authorize(principal: Principal, resource: str, operation: str, record=None) -> bool:
    return True  # Replace with your actual policy.

auth = CallbackAuth(login=login, resolve=resolve, authorize=authorize)
```

For a hosted IdP such as Auth0/OIDC, define `CallbackAuth(login_token=your_verified_token_callback)` and register a custom React login screen. The callback must validate issuer, audience, signature, lifetime and intended tenant; **never trust roles or claims supplied directly by the browser**. The `/admin/auth/external` endpoint exchanges a verified token for an admin session; Pyntral does not implement the provider's OAuth redirect flow for you.

## `Principal` and `currentAdmin`

`Principal` fields are `id`, `username`, `roles`, optional `display_name`, `email`, and scalar `attributes`. `.as_dict()` exposes normalized `name` and `role` as well. It does not require a local database account: a callback can return a principal derived from an external provider.

```tsx
import { useCurrentAdmin } from "@pyntral/auth";

export default function AccountBadge() {
  const admin = useCurrentAdmin();
  return <span>{admin?.name || admin?.username}</span>;
}
```

Do not embed secrets, session tokens, or arbitrary personal information in `attributes`: currentAdmin is browser-visible. For roles, use the server-side policy in [authorization](authorization.md).

## Security constraints

- Sessions use signed cookies; use HTTPS and secure cookie flags outside localhost.
- Write operations require `X-CSRF-Token`; the bundled API client handles it.
- The server resolves the principal for each authenticated request and enforces permissions separately from UI visibility.
- If you run multiple servers, use the same durable session secret across replicas.
- Admin sessions are not a replacement for API authentication of unrelated host routes.

See [deployment](deployment.md) and [security policy](../SECURITY.md).
