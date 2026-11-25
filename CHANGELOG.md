# Changelog

Pyntral releases follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) conventions and use [PEP 440](https://peps.python.org/pep-0440/) version numbers.

## Unreleased

- Place standard CRUD before slots below the page heading by default; configure legacy placement or hide the stock title per CRUD mode without removing actions.

- Add optional searchable sidebar navigation with preserved tree expansion.
- Add authenticated custom home and category dashboards with a shared default view and user context.
- Add theme-aware CodeBlock and JsonView with language detection, optional highlighting, lossless JSON formatting, clipboard and collapse controls.

## 1.0.0b3 — Third public beta

- Add public Tabs and table primitives reused by built-in CRUD.
- Add before/after CRUD slots and default view composition.
- Support composite primary key CRUD with canonical record identities, scoped relations, actions, audit and uploads.
- Add custom transactional create/update handlers and bounded binary RPC bridges.
- Add portable custom SPA export and a Python-only Docker deployment recipe.
- Render configured browser title and favicon, including reverse-proxy mounts.
- Document the public HTTP client with explicit same-origin host scope.
- Share CRUD operation context across hooks and handlers; retain update events after flush.

## 1.0.0b2 — Second public beta

### Added

- Declarative CRUD and action hooks, calculated and write-only fields, Pydantic validation, dependent selects and optimistic concurrency.
- Composable password, soft-delete, timestamp, audit and upload features. Authenticated attachments support local storage and an optional S3/MinIO backend.
- Conditional field and operation policies, CSV/JSON export, configurable form layouts, table preferences and filter presets.
- Localization, per-admin theme settings and reusable choice, popover, sortable and mock file-picker controls.
- Configurable centered/split login screen, shared application branding, password visibility, pre-authentication theme tokens and localization, and optional login-specific theme tokens.
- Declarative sidebar configuration with configurable dimensions, resizing, header/footer branding, dynamic Lucide icons, SVG/image icons and custom React region/item slots.
- Public FileRow, Collapsible and OverflowText primitives, reused by built-in attachments, layouts and navigation.
- Optional SSE invalidation, in-process jobs with progress and cancellation, and CLI resource schema documentation.

### Fixed

- Keep the dev supervisor and Vite alive during Python reloads on Windows; isolate child process groups and recover backend startup failures after the next edit.

- Keep the original edit version across realtime refreshes and return HTTP 412 on stale writes.
- Apply field and selection policies across exports, searches, and relation selectors.
- Run authorization, validation, setters, hooks and audit through the same transaction for standard and related creation. Encode mutation responses before committing.
- Detach attachments transactionally and retry storage cleanup. Release job slots on early cancellation and close both Kafka clients after a consumer failure.
- Preserve FastAPI lifespan state, serve production bundles under custom mounts and proxy prefixes, and bound JSON input and event publication.
- Derive missing accent-dependent theme tokens, keep hover borders consistent, and share primary foreground contrast across controls. Bundle English, French and German UI messages; other locales remain configurable.
- Improve responsive record layouts, attachment picker/list presentation and nested navigation indentation.
- Support server-side session revocation with an in-memory default and an optional shared store. Fix Unicode usernames and improve keyboard interaction in dialogs, tabs and mobile navigation.

### Upgrade notes

- Sign in again after upgrading. Pyntral stores new sessions in memory by default and requires no session table or migration. Replicated deployments can supply a shared `SessionStore`.
- The sidebar header now inherits Admin.title by default; configure SidebarHeader to retain a different brand name or logo. Existing kebab-case icon names remain supported.
- Rebuild a custom SPA to pick up the runtime mount path, UI changes and new API contracts. The generic SPA ships in the wheel.
- Deploy and validate the broker, S3/MinIO, PostgreSQL and multi-worker options in your own environment. The [release readiness guide](docs/deployment.md#release-readiness) lists the beta verification scope.

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

