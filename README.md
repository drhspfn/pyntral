<div align="center">

# Pyntral

**A React-powered admin console for FastAPI and SQLAlchemy.**

Define your resources in Python. Get a searchable, customizable administration interface without writing CRUD screens.

**Python 3.11+** · **FastAPI** · **SQLAlchemy 2.x** · **React 19** · **TypeScript** · **MIT**

`1.0.0b2` · **Second public beta** · [Get started](docs/getting-started.md) · [Documentation](docs/README.md) · [API reference](docs/api-reference.md)

</div>

---

## Why Pyntral?

Pyntral attaches a React single-page administration UI to an existing FastAPI application. SQLAlchemy mappings provide field types, relationships, and validation metadata; Python owns authentication, authorization, CRUD operations, and custom actions. React renders responsive forms, tables, filters, and extension components.

- **Model-driven CRUD** — register SQLAlchemy models, configure fields and relations, and manage records through one API.
- **Practical filtering** — type-aware operators, numeric/date ranges, enum include/exclude, and searchable foreign keys.
- **Built to extend** — nested navigation groups, custom pages, record actions, dialogs, field renderers, and a shared React component kit.
- **Python-configured branding** — centered or split login, public light/dark theme configuration, sidebar layouts, SVG and theme-specific image logos, dynamic Lucide icons, configurable navigation sizing, and optional TSX header/footer/item slots.
- **Authentication and access controls** — local credentials, SQLAlchemy-backed users, external identity callbacks, role thresholds, field visibility, and server-side authorization.
- **Typed Python ↔ React operations** — authenticated Pydantic bridges with generated TypeScript clients.
- **Event-oriented** — metadata-only events with in-process, optional RabbitMQ, or optional Kafka transports.
- **Developer-friendly** — `uv` workflows, Vite HMR, content-addressed frontend build caching in `.pyntral/`, and structured logging.

> **Release status:** The second beta targets single-worker integrations. Live PostgreSQL, broker and S3/MinIO deployments, along with multi-worker SSE, require validation in your environment. See [release readiness](docs/deployment.md#release-readiness).

## Quick start

For a regular installation, only **Python 3.11+** is required. **Node.js 22.12+ and npm are needed only to compile custom React extensions** or develop Pyntral itself.

```bash
# From this repository
uv sync --extra dev
uv run pyntral init-env
uv run pyntral dev examples.shop.app:app
```

Open **http://127.0.0.1:5173/admin/** and sign in with the local account created by `init-env`. This demo seeds an example SQLite shop; it is not intended for real business data.

For live bridge types and VS Code autocomplete without rebuilding React:

```bash
uv run pyntral types examples.shop.app:app --editor
uv run pyntral types examples.shop.app:app --watch
```

For a production SPA build (ESLint checks on core and registered extensions, strict TypeScript and Vite):

```bash
uv run pyntral build --force
# Bundle: .pyntral/dist/
```

Install the **published Python package** in a FastAPI application:

```bash
uv add pyntral
# Alternative:
pip install pyntral
```

The default admin SPA is **already compiled into the Python wheel**. No npm install or `pyntral build` is necessary for normal SQLAlchemy resources, filters, auth, actions or declarative sidebar branding. See the [minimal Python-only example](examples/basic/README.md).

For applications with custom TSX fields, pages, dialogs or themes, use the *same Python dependency*, plus Node.js **at development/build time**:

```bash
uv add pyntral
uv run pyntral types your_app.main:app --editor
uv run pyntral build --app your_app.main:app
```

The resulting `.pyntral/dist/` overrides the packaged generic SPA for that application. See [custom extensions](docs/extensions.md) and [publishing](docs/publishing.md).

When working **inside this repository**, use `uv sync --extra rabbitmq` instead of adding Pyntral as its own dependency.

## Define resources in Python

```python
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pyntral import Admin, LocalAuth, Resource, Field

from your_app.models import User, Order

engine = create_engine("sqlite:///./app.db")
SessionLocal = sessionmaker(engine, expire_on_commit=False)
app = FastAPI()

admin = Admin(
    app,
    session_factory=SessionLocal,
    auth=LocalAuth.from_env(),
    secret_key="replace-with-a-secret-at-least-32-characters-long",
    secure_cookie=False,  # LOCAL HTTP ONLY; use True behind HTTPS
    title="My workspace",
)

admin.add_resource(Resource(
    User,
    visible_name=User.email,
    search_fields=["email"],
    fields={"password_hash": Field(visible=False)},
))
admin.add_resource(Resource(Order))
```

For deployable applications, supply secrets from environment variables and set `secure_cookie=True` under HTTPS. The complete runnable integration is in [`examples/shop/app.py`](examples/shop/app.py).

## Customize the sidebar

```python
from pyntral import SidebarConfig, SidebarHeader, SvgIcon

sidebar = SidebarConfig(
    width=260,
    header=SidebarHeader(
        title="My workspace",
        subtitle="Operations",
        icon=SvgIcon.from_file("assets/logo.svg"),
        icon_background=False,
    ),
    dashboard_icon="house",
)
# Pass sidebar=sidebar to Admin(...)
# Resource(Order, icon="shopping-cart") also accepts SvgIcon or ImageIcon.
```

The packaged generic SPA reads this configuration from the API at runtime.
See [sidebar and icon API](docs/api-reference.md#sidebar-and-icon-configuration),
[UI customization](docs/ui.md#sidebar-branding-and-navigation-icons), and
[sidebar TSX slots](docs/extensions.md#sidebar-extensions).

## How it fits together

```text
FastAPI app
  └─ Pyntral Admin (/admin)
      ├─ Auth, permissions, typed CRUD and relationship API
      ├─ Resource / page / action / bridge registries
      ├─ Optional metadata-only event transports
      └─ React SPA
          ├─ Type-aware tables, filters and forms
          ├─ UI primitives and theme tokens
          └─ Registered TSX extensions

PyPI wheel → bundled generic SPA → FastAPI
Custom TSX (optional): uv / npm → Vite → .pyntral/dist → FastAPI
```

Your ORM definitions remain in Python. Resource metadata is delivered at runtime; adding another model does **not** require rebuilding React. Adding a new TypeScript extension does require the frontend compiler (handled by the CLI).

## Documentation

| Start here | Customize | Operate |
| --- | --- | --- |
| [Installation & first app](docs/getting-started.md) | [Resources & relations](docs/resources.md) | [CLI & build cache](docs/cli.md) |
| [Architecture](docs/architecture.md) | [Filters](docs/filters.md) | [Logging](docs/logging.md) |
| [Python & HTTP API](docs/api-reference.md) | [React UI & theming](docs/ui.md) | [Events & brokers](docs/events.md) |
| [Authentication](docs/authentication.md) | [Custom components](docs/extensions.md) | [Deployment](docs/deployment.md) |
| [Authorization](docs/authorization.md) | [Typed bridges](docs/bridges.md) | [Troubleshooting](docs/troubleshooting.md) |

See the [complete documentation index](docs/README.md), [changelog](CHANGELOG.md), and [contribution guide](CONTRIBUTING.md).

## Development

```bash
uv sync --extra dev
uv run pytest -q
uv run pyntral doctor
uv run pyntral build
```

The build command runs ESLint, TypeScript and Vite when developing custom frontend extensions. Release CI separately builds a generic SPA and bundles it in the PyPI wheel; consumers do not need Node.js for the standard admin. The tracked repository intentionally omits credentials, databases, generated assets, and `uv.lock` (to be generated and committed by the maintainer).

## Security & support

Never expose the admin API without authentication and HTTPS. Resource authorization is enforced server-side; hiding navigation items is only a presentation choice. Event payloads contain identifiers and field metadata, **not field values**. Read [security guidance](SECURITY.md) before deploying; report vulnerabilities privately, not in public issues.

## License

[MIT](LICENSE). Pyntral is an independent project; it is not affiliated with AdminJS.

## Docker smoke test

Build and run the production shop example (no Vite dev server):

```bash
docker compose -f examples/shop/compose.yaml build --progress=plain
docker compose -f examples/shop/compose.yaml up -d
```

The image build runs ESLint, strict TypeScript checking, and Vite. See the
[shop Docker example](examples/shop/README.md) for setup and verification.

## CI and publishing

Add the `Run checks` label to start PR CI. It reruns on pushes while the label is present. Releases are published as **Python wheels and source distributions on PyPI** using GitHub OIDC Trusted Publishing. The compiled generic React SPA is packaged inside the Python distribution; no npm package is published. See [release setup](docs/publishing.md).

The sign-in screen also accepts `Admin(login=LoginConfig(...))`, inherits
the same application branding, and applies global theme tokens before
authentication. See [login customization](docs/ui.md#login-screen-customization).
