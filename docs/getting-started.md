# Installation and first integration

[Documentation index](README.md) · [CLI](cli.md) · [Resources](resources.md)

## Requirements

- Python 3.11 or later and `uv` (recommended for dependency management).
- Node.js 22.12+ with npm **only** for library development or when compiling custom TSX extensions. Neither is needed for the default published Python package.
- FastAPI, SQLAlchemy 2.x, Pydantic 2.x (installed with the package).
- An application-owned SQLAlchemy engine, models, and session factory.

Pyntral does not create tables or migrations for your application. Use your normal SQLAlchemy/Alembic migration strategy.

## Run the included example

```bash
uv sync --extra dev
uv run pyntral init-env
uv run pyntral doctor
uv run pyntral dev examples.shop.app:app
```

`init-env` interactively asks for the password and writes a **gitignored** `.env` file. The demo loads these environment variables through the CLI. The frontend is served by Vite at <http://127.0.0.1:5173/admin/> and the backend by Uvicorn at <http://127.0.0.1:8000/admin/>.

The example creates and seeds `shop.db` locally on application startup. Delete the database only when you want to reset the example; never copy its data into production. The shop intentionally has restrictive foreign keys: deleting a customer with orders (or an order with items) may produce HTTP 409.

## Use it in your application

Install `pyntral` from your published package source (when available) or use an editable local installation during development. Create your own `FastAPI` app and `sessionmaker` and register resources:

```python
import os
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pyntral import Admin, LocalAuth, Resource, Field

from app.models import Customer  # your SQLAlchemy mapped model

engine = create_engine(os.environ["DATABASE_URL"])
SessionLocal = sessionmaker(engine, expire_on_commit=False)
app = FastAPI()

admin = Admin(
    app,
    session_factory=SessionLocal,
    auth=LocalAuth.from_env(),
    secret_key=os.environ["APP_SECRET_KEY"],
    path="/admin",
    secure_cookie=True,
    title="Operations",
)
admin.add_resource(Resource(
    Customer,
    search_fields=["name", "email"],
    list_fields=["id", "name", "email"],
    fields={"secret_note": Field(visible=False)},
))
```

Provide `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH` and `APP_SECRET_KEY` securely. Generate a password hash using `pyntral hash-password` and a strong secret with `python -c 'import secrets; print(secrets.token_urlsafe(48))'`. Do not commit these values. For localhost HTTP only, configure `secure_cookie=False`; production requires HTTPS.

The library can mount multiple resources and pages. Pyntral expects the caller to create the SQLAlchemy tables and manage schema migrations. Adding a resource registers its API routes logically through the resource registry; no extra frontend compilation is required for Python-only metadata changes.

## Build a customized SPA (optional)

```bash
uv run pyntral build --app app.main:app --base /admin/
```

This step is **not needed for standard PyPI installations**. It creates `.pyntral/dist/` containing your custom frontend extensions; you can then run your normal ASGI server (for example, `uvicorn app.main:app`) from the project directory. If the output lives elsewhere, set `PYNTRAL_DIST=/absolute/path/to/dist` or pass `dist_dir` to `Admin`.

For custom components use [`pyntral.components.json`](../pyntral.components.json) as a template. See [extensions](extensions.md), [bridges](bridges.md), and the [build guide](cli.md).

## Notes on external projects

- Inside the Pyntral repository use `uv sync --extra dev`, `--extra rabbitmq`, or `--extra kafka`.
- In a separate consumer project, after the name has been published on the package index, use `uv add pyntral`, `uv add 'pyntral[rabbitmq]'`, etc.
- This repository does not assume the package or a public GitHub repository is already published.

## Deployment modes

The published Python wheel serves the **standard SPA** automatically at `/admin/`, so there is no npm, Vite or separate frontend deployment for ordinary integrations.

If you register **custom TSX extensions**, install Node.js in the development or build environment and run `pyntral build --app your.module:app`. Deploy the resulting `.pyntral/dist/` with your application, or configure `Admin(dist_dir=...)`. Production containers can still be Python-only. See [extensions](extensions.md) and [deployment](deployment.md).
