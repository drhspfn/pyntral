# Deployment and release readiness

[Documentation index](README.md) · [Security policy](../SECURITY.md)

Pyntral is a beta library. Prepare and verify the production SPA separately from your FastAPI service. Your application owns database schema migrations, user management, reverse proxy configuration, and secrets.

## Production build

```bash
uv sync --extra dev
uv run pyntral build --app your_app.main:app --base /admin/
```

**Standard PyPI installation:** the wheel contains a precompiled generic bundle (`pyntral/web_dist`). No Node/npm or local frontend build is required.

**Customized installation:** `pyntral build --app your.module:app` writes `.pyntral/dist/`. On deployment, preserve the generated `index.html` and `assets/` together. Set the bundle location with `Admin(dist_dir=...)` or `PYNTRAL_DIST`. Start the host ASGI app using its normal deployment command and proxy HTTPS traffic to it.

The build output is tied to the base path. If you mount at `/ops`, build with `--base /ops/`. The mounted FastAPI sub-app serves the SPA history fallback so client routes are reachable directly.

## Secrets and cookies

- Supply `APP_SECRET_KEY` with a stable, cryptographically random value of at least 32 characters; do not commit it.
- Use `Admin(secure_cookie=True)` behind HTTPS (the default). `False` is for local HTTP testing only.
- Keep identity provider signing keys and message-broker credentials outside the repository.
- Avoid publishing generated `.env`, `.pyntral/`, local SQLite databases, and logs.
- Configure login rate limiting and monitoring at the host or reverse proxy layer as appropriate; Pyntral does not provide a complete identity-security platform.

## Database and authorization

Use Alembic for controlled SQLAlchemy schema migrations; `Resource` registration alone does not migrate tables. Configure explicit deletes/cascades or application-level archive actions. Retain restrictive foreign key constraints unless your data model explicitly calls for cascades.

Check resource `RoleAccess`, `AuthBackend.authorize`, row scopes, field policies and custom bridge handlers in every deployment. A hidden sidebar entry is **not** an authorization boundary. Do not expose admin endpoints to unauthenticated public clients.

## Multiple instances and event transports

The default event bus is process-local. For multiple workers, use RabbitMQ or Kafka with appropriately configured consumer groups/queues; follow [events](events.md) for ACK/retry behavior. Events are emitted after CRUD commit but **without** a transactional outbox; a crash can lose events during the commit-to-publish interval. Add an external reliability layer before relying on events as an audit ledger or financial system source of truth.

The application and broker workers should reuse consistent connection and identity policies. Configure DLQ/dead-letter handling for RabbitMQ externally. Live broker tests are required before production use.

## Release readiness

Confirmed in the local development workflow: Python integration tests, Python package building and import checks (see release notes for exact results). The frontend has been syntax-checked previously, but full browser acceptance tests and a live RabbitMQ/Kafka test matrix are **not** claimed for this beta.

Before publishing a stable release, complete:

1. `uv lock` and commit the reviewed Python lockfile.
2. Produce/commit a reviewed frontend lockfile and validate `npm ci` / `pyntral build` on Windows and Linux.
3. Run Playwright or equivalent browser tests covering sign-in, filters, related records, permissions, custom actions, dialogs and themes.
4. Run broker integration tests with real RabbitMQ/Kafka containers and failure/reconnect cases.
5. Audit authentication, CSRF, data exposure in bridge handlers, RBAC and dependency vulnerabilities.
6. Reserve the PyPI project name, configure publishing credentials, set canonical repository/docs URLs in `pyproject.toml`, and tag a release.

The name and version in this repository are **not** proof that a distribution has been uploaded to PyPI.
