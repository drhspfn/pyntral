# Troubleshooting

[Documentation index](README.md)

## `uv` refuses `pyntral` as a self-dependency

You are inside the Pyntral repository. Install repository extras with:

```bash
uv sync --extra dev --extra rabbitmq
# Or
uv sync --extra kafka
```

Use `uv add 'pyntral[rabbitmq]'` only from a **different** project after Pyntral has been published.

## `npm` is not found / WinError 2

Install Node.js 22.12+ and verify `node --version` and `npm --version` in the same PowerShell session. Pyntral uses `npm.cmd` on Windows and `npm` elsewhere. Retry `uv run pyntral doctor` and `uv run pyntral dev examples.shop.app:app`.

## Dev exits after a Python file changes (Windows)

Older builds delegated reloads to Uvicorn's Windows reloader, which could
deliver a console interrupt to the CLI and Vite. Current `pyntral dev`
supervises both servers and restarts only the backend. If a Python edit
causes an import/startup failure, the backend logs the error while the
watcher remains alive; save the corrected file to retry. Vite continues
to handle TSX HMR independently. Ctrl+C intentionally stops both servers.

## SPA displays 404 or a blank page

Check that `uv run pyntral build --force` generated `.pyntral/dist/index.html` and the `assets/` directory. For production, verify the configured `Admin.path`, any ASGI `root_path` set behind a proxy, and the selected bundle directory. Rebuild a custom bundle made before 1.0.0b2. For Vite development, match `pyntral dev --base` to the admin mount. If serving from another directory, configure `PYNTRAL_DIST` or `dist_dir`.

## Your TSX extension is not found

Check spelling and casing of `pyntral.components.json`, the category (`fields`, `pages`, `actions`, `dialogs`, `profile`, `access`, `auth`, `themes`) and the local relative path. No extension may resolve outside the project root. Rebuild after source changes. For generated bridge imports run `uv run pyntral types module:app`.

## Record deletion fails with 409

Database foreign keys or uniqueness constraints prevent the operation. For example, an Order can have OrderItems referencing it, and a Customer can have Orders. Pyntral deliberately does not delete related rows automatically. Configure SQLAlchemy/database cascades deliberately or use a custom archive/soft-delete action.

## A deleted related record still appears in the UI

Try a full reload to distinguish a stale client query cache from a failed mutation. The bundled React implementation should invalidate affected list/relationship queries on supported CRUD mutations. Check whether a custom component is using its own independent query keys, and whether the server returned 200/409/404. Custom components own invalidation for their own custom data sources.

## A custom event or field does not appear in logs

Check the channel threshold, the event's `level`, and the Python logger's effective level. For example, `admin.log_event("events", "custom", level="DEBUG")` is suppressed by an INFO channel until you enable `events=DEBUG`. Uvicorn startup messages come from `uvicorn.error`; request access lines come from `uvicorn.access`.

## `FastAPI` has no `add_event_handler`

Pyntral composes the parent FastAPI application's ASGI lifespan for EventBus startup and shutdown. If you encounter a lifespan error, check that the host application uses a compatible FastAPI version and that the broker configuration is valid.

## Broker adapter raises missing dependency

Inside the repo use `uv sync --extra rabbitmq` or `uv sync --extra kafka`. In a consumer project install the relevant optional extra. Runtime errors from an unavailable broker are separate: verify connection URL, permissions, queue/topic availability and retry strategy.

## Type errors or invalid Pydantic bridge output

Bridge inputs and outputs are validated according to their Pydantic models. Update your model and regenerate types; ensure the handler returns the declared output type and does not leak sensitive data. Review the HTTP error code and `X-Request-ID` in the relevant `pyntral.bridge` / `pyntral.http` log.

## Cache resets

Remove the generated UI files under `.pyntral/` and rebuild. Preserve
`.env`, your database and any attachment directory such as the Shop example's
`.pyntral/uploads/`. Keep the committed `uv.lock` when rebuilding from a release checkout.
