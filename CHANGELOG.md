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
