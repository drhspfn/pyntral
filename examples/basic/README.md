# Minimal Python-only FastAPI integration

Copy this example into a separate uv project and install the **`pyntral` Python wheel** there. Use a released wheel or one built locally from this checkout. The compiled React SPA is embedded in that wheel: **no Node.js, npm, Vite or frontend build is needed**.

```bash
uv add --prerelease allow 'pyntral==1.0.0b2'
# Or use: uv add /path/to/pyntral-1.0.0b2-py3-none-any.whl
# set ADMIN_USERNAME, ADMIN_PASSWORD_HASH, APP_SECRET_KEY (at least 32 chars)
uv run uvicorn examples.basic.app:app --host 127.0.0.1 --port 8000
```

For local HTTP development, also set `ADMIN_SECURE_COOKIE=false`. Use `pyntral hash-password` to generate a local password hash. Visit <http://127.0.0.1:8000/admin/>. Pyntral serves its generic SPA and standard CRUD for `Customer` automatically.

For the **custom-component** workflow, see [`../shop/`](../shop/README.md). That example adds TSX extensions and therefore compiles an application-specific bundle once at build time. Both use **the same PyPI package**.

Do not use `Base.metadata.create_all` instead of proper migrations in a production application.
