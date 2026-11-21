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
