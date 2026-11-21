# Contributing to Pyntral

Thanks for your interest in improving Pyntral. The project is in early beta and welcomes focused bug reports, tests, documentation improvements and reviewed pull requests.

## Local setup

```bash
uv sync --extra dev
uv run pytest -q
uv run pyntral doctor
uv run pyntral init-env
uv run pyntral dev examples.shop.app:app
```

Node.js 22.12+ is required to build the React UI. The CLI stages files under `.pyntral/`; never commit this generated directory, `.env`, local databases, or credentials.

## Code organization

- `src/pyntral/`: Python public API, session handling, ORM adapter, filtering, CLI, observability and event transports.
- `src/pyntral/ui/`: React/TypeScript SPA, shared controls and theme tokens.
- `admin/`: illustrative extension components.
- `examples/shop/`: working FastAPI + SQLite demonstration.
- `examples/events/`: broker worker patterns.
- `tests/`: Python integration tests and contracts.
- `docs/`: maintained documentation, API examples and deployment notes.

## Change process

1. Start from a branch and keep changes scoped to one feature or bug.
2. Preserve backward compatibility within a published release series; document breaking changes explicitly.
3. Add tests for API, authorization and event behavior changes. Never weaken CSRF/ACL tests to make a feature pass.
4. Run `uv run pytest -q` and, when Node/npm are available, `uv run pyntral build --force`.
5. Update the appropriate `docs/` page, README pointers and `CHANGELOG.md`.
6. Use descriptive commits (for example `fix(ui): preserve select value when operator changes`).

Before publishing a release, generate and review `uv.lock`, review frontend lockfiles, test a built wheel (not only source imports), and validate the SPA in a real browser. The release manager should verify ownership/availability of package names and URLs.

## Reporting bugs

Provide OS, Python/Node versions, version or commit, relevant redacted logs, a minimal reproduction, and expected/observed behavior. Remove secrets, session cookies, PII and database content. For security issues, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.
