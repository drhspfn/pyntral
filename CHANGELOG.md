# Changelog

Pyntral releases follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) conventions and use [PEP 440](https://peps.python.org/pep-0440/) version numbers.

## 1.0.0b1 — Initial public beta

### Features

- FastAPI and SQLAlchemy 2.x resource registry with model-driven CRUD and relationships.
- React SPA with type-aware filters, relation selectors, forms, light/dark themes, toasts, dialogs, and customizable UI components.
- Local, model-based, and callback authentication with server-side resource, record, and field permissions.
- Pydantic bridges with generated TypeScript clients for custom React integrations.
- Structured logging with per-channel configuration and optional Loguru integration.
- Metadata-only events with an in-process bus and optional RabbitMQ and Kafka transports.
- Developer CLI with Vite integration, frontend caching, and a runnable sample application.
- English documentation, usage examples, contributor guidance, and a security policy.
- Watchable Pydantic bridge declarations, VS Code editor configuration, label-gated PR checks, and OIDC PyPI release workflow.

### Known limitations

- Full browser E2E and live RabbitMQ/Kafka integration tests are not yet part of the verified release matrix.
- Transactional outbox, built-in broker dead-letter queue management, stable frontend lockfile, and published documentation hosting are future work.

See [release readiness](docs/deployment.md#release-readiness) for verification requirements.

- PyPI-first release pipeline embeds the generic SPA inside wheel/sdist; custom TSX builds remain optional for consuming applications.

- Add guarded CRUD lifecycle hooks with consistent before/after commit semantics.

- Add offline resource schema reference generation in Markdown/JSON (`pyntral schema`).

- Add secure Bridge-backed dependent Select fields, including a validated Shop shipping location demo.

- Add optional authenticated SSE invalidation of frontend query caches, without record identifiers or values.

- Add opt-in in-process background resource jobs with bounded execution, progress and cancellation, demonstrated in Products.

- Add before/after hooks around record, bulk and resource Actions, including server-side veto support.

- Add reusable accessible Checkbox, CheckboxGroup, Switch, RadioGroup and ToggleGroup controls, a compact table Columns panel and unified bulk-selection checkboxes.

- Add public accessible `SortableList` drag handles; use in table Columns and the Shop component playground.



### Beta fixes

- Preserve the original edit version across realtime refreshes and manage version columns on the server.
- Apply contextual read and select policies to searches, exports, and relation pickers.
- Apply one create transaction to standard and related records, including scope, hooks, validation, and auditing.
- Retry storage cleanup after attachment or owner deletion.
- Preserve timestamp field policies, mask password inputs, and release slots when queued jobs are cancelled.

- Preserve host lifespan state and serve installed SPA bundles under custom mount paths and proxy prefixes.
- Add revocable in-memory sessions with an optional shared store, bounded request bodies and event publication, and an async database deployment check.
- Restore keyboard focus in confirmation dialogs, record tabs, and the mobile navigation drawer.
