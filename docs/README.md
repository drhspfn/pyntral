# Pyntral documentation

Pyntral is an early-stage Python-admin framework with a React frontend. These guides describe the implementation shipped in this repository, not a planned API.

## Getting started

1. [Installation, demo, and first integration](getting-started.md)
2. [Architecture and request lifecycle](architecture.md)
3. [Python classes, methods, and HTTP endpoints](api-reference.md)

## Backend configuration

- [Resources, fields, relationships, actions, and pages](resources.md)
- [Authentication (local, ORM, callbacks, external tokens)](authentication.md)
- [Role-based and record-based authorization](authorization.md)
- [Filter operators and query format](filters.md)
- [Pydantic bridges and generated TypeScript](bridges.md)
- [Typed events, delivery guarantees, RabbitMQ, Kafka](events.md)
- [Structured logs and Loguru integration](logging.md)

## Frontend customization

- [UI component library and theme tokens](ui.md)
- [Login screen customization](ui.md#login-screen-customization)
- [Sidebar branding, icons, and resizing](ui.md#sidebar-branding-and-navigation-icons)
- [Custom fields, pages, dialogs, menus, and actions](extensions.md)
- [Sidebar extension slots](extensions.md#sidebar-extensions)

## Running and contributing

- [CLI, dev workflow, and frontend build cache](cli.md)
- [Deployment and release readiness](deployment.md)
- [Troubleshooting](troubleshooting.md)
- [Contributing](../CONTRIBUTING.md) · [Changelog](../CHANGELOG.md) · [Security](../SECURITY.md)

The minimal Python-only example is [`examples/basic/`](../examples/basic/README.md). The customizable example is [`examples/shop/app.py`](../examples/shop/app.py), with TSX extensions under [`admin/`](../admin/) and broker worker examples under [`examples/events/`](../examples/events/).

- [Publishing the Python package to PyPI](publishing.md)

## Beta 3 extension APIs

- [Tabs and tables](ui.md#tabs-and-tables)
- [CRUD slots and default view](extensions.md#compose-standard-crud-views)
- [Composite primary keys](resources.md#composite-primary-keys)
- [Custom transactional writes](resources.md#custom-transactional-writes)
- [Binary bridge uploads](bridges.md#binary-uploads-with-typed-rpc)
- [Browser branding](ui.md#browser-title-and-favicon)
- [Public HTTP client](extensions.md#http-client-pyntralapi)
- [Portable custom UI](deployment.md#custom-ui-in-a-python-only-runtime)

## Beta 4 navigation and presentation

- [Sidebar search](ui.md#sidebar-search)
- [Home and category dashboards](extensions.md#home-and-category-dashboards)
- [CodeBlock and JsonView](ui.md#codeblock-and-jsonview)

- [CRUD heading visibility and slot placement](extensions.md#heading-visibility-and-slot-placement)
- [Dashboard authorization](authorization.md#dashboard-authorization)
