# Pyntral — development instructions

These instructions apply to contributors and coding agents across the repository. Also read [CONTRIBUTING.md](CONTRIBUTING.md) and the closest directory-specific `CLAUDE.md` before editing.

## Product and architecture

Pyntral is a **Python-first** FastAPI/SQLAlchemy admin library with a React implementation. The generic React SPA must be bundled into the **PyPI wheel** so that `pip install pyntral` / `uv add pyntral` works without Node.js or a frontend build. A separate, optional build supports application-specific TSX extensions.

- Keep Python as the source of truth for authorization, resources, validation, relational operations and event contracts. The frontend never grants permissions.
- Preserve both modes: an install-and-run generic admin, and an application-specific TSX build. Do **not** introduce npm publication or a standalone SDK as a replacement for PyPI distribution.
- Reuse existing ORM adapters, schema/bridge code, shared UI primitives, feedback components, theme tokens and event transports instead of reimplementing them.
- Keep public API backward compatible where feasible. Explicitly document breaking changes.
- Respect synchronous and asynchronous SQLAlchemy sessions, CSRF, row scopes, and per-resource/per-field ACL. Detaching a relationship is not deleting its target.
- Avoid broad exception suppression, silent fallbacks, unchecked casts, `any`-to-silence-compiler-errors, disabling TS strictness, and speculative refactors.
- Handle loading, errors, empty states, accessibility, keyboard focus, responsive layouts and optimistic mutation rollback.

## Required feature showcase — merge gate

**Every new user-visible feature MUST have a real, reachable demonstration in `examples/shop/` in the SAME PR.** A passing isolated test is not a substitute for a usable demonstration.

1. Register the feature in `examples/shop/app.py`. For React work, add an actual component under `admin/` and register it in `pyntral.components.json`.
2. Provide reproducible demo data. Make new seed routines safe on existing `shop.db` without truncating or overwriting customer data.
3. Update `examples/shop/README.md` with concrete navigation, actions to try and expected results.
4. Add automated tests for correct behavior, error handling, and authorization. For visual features, also check integration with the demo (and run a browser check when possible).
5. Update relevant `docs/` pages, main README references when affected, and `CHANGELOG.md` for user-visible changes.

Do not label a feature complete if it is not reachable in the demo. An exception requires explicit maintainer approval and a reason documented in the PR.

## Security, data and logging

- Never commit `.env`, passwords, API keys, sessions, databases, `.pyntral/` or `node_modules/`.
- Server handlers must validate inputs and permissions, not rely on hidden buttons or frontend-only checks.
- Events should carry IDs and metadata rather than sensitive field values. Do not leak request bodies, credentials, or personal data into logs.
- Avoid unbounded bulk updates and unchecked multi-tenant access. Separate attach/detach/create operations; preserve transactional integrity.

## Verification

Run the checks relevant to the change. Be precise about which actually ran:

```bash
uv sync --extra dev
uv run pytest -q
node --experimental-strip-types --test src/pyntral/ui/tests/*.test.mjs
uv run pyntral types examples.shop.app:app --editor
uv run pyntral build --app examples.shop.app:app --force
```

For packaging changes, build the **generic** SPA into the wheel and check `scripts/smoke_installed.py` on the installed wheel, not source imports. For frontend changes, run the customized Shop build; when available, verify the UI in a browser. Distinguish these two builds explicitly.

PR CI runs **only after adding the `Run checks` label**. To rerun after a new commit, remove and re-add the label.

## Pull requests and releases

- Use a feature branch; do not push to `main` or publish a release unless requested.
- Keep one scope per PR, include a Shop demo checklist and actual test evidence using [the PR template](.github/pull_request_template.md).
- Update documentation and test evidence alongside code, not in an indefinite follow-up.
- Do not rewrite repository history, change distribution channels, or create release tags as part of an ordinary feature PR.
