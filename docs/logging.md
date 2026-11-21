# Structured logging and observability

[Documentation index](README.md) · [CLI](cli.md)

Pyntral emits structured Python `logging` records under `pyntral.*` and does not modify the host application's root logger implicitly. The CLI opts in to console formatting; applications can integrate their own sinks. Normal HTTP access logs are emitted by `uvicorn.access`, not Pyntral.

## Channels

`auth`, `security`, `resource`, `action`, `bridge`, `http`, `lifecycle`, and **`events`**. Each channel supports level overrides; `LoggingConfig.events` can disable individual event names.

```python
from pyntral import Admin, LoggingConfig, configure_logging

configure_logging(
    level="INFO", format="json", file="logs/admin.jsonl",
    channel_files={"security": "logs/security.jsonl", "events": "logs/events.jsonl"},
    max_bytes=10_000_000, backup_count=5,
)

admin = Admin(
    app, session_factory=SessionLocal, auth=auth, secret_key=secret,
    logging_config=LoggingConfig(
        level="INFO", channels={"events": "DEBUG", "bridge": "OFF"},
        http="errors", slow_request_ms=750,
        events={"resource.deleted": False},
    ),
)
```

`configure_logging()` attaches **package-owned** handlers only. It accepts `format="compact" | "json"`, `console`, `template`, `stream`, `formatter`, per-channel files, and rotation settings. Call `stop_logging()` when removing managed handlers. The host can instead configure the `pyntral` logger with stdlib handlers directly.

## CLI examples

```bash
uv run pyntral dev examples.shop.app:app --uvicorn-log-level WARNING
uv run pyntral dev examples.shop.app:app --log-channel events=DEBUG --log-channel bridge=OFF
uv run pyntral dev examples.shop.app:app --log-http slow --slow-request-ms 500
uv run pyntral dev examples.shop.app:app --log-format json --log-file logs/admin.jsonl
uv run pyntral dev examples.shop.app:app --log-channel-file events=logs/events.jsonl
```

`--log-level` controls package events; `--uvicorn-log-level` independently controls Uvicorn's error/startup messages. Per-request `uvicorn.access` logging is off in the Pyntral CLI unless you pass `--access-log`.

## Optional Loguru sink

```bash
uv sync --extra loguru
```

```python
from loguru import logger
from pyntral import forward_to_loguru

logger.add("logs/pyntral.log", rotation="10 MB", retention="14 days", enqueue=True)
handler = forward_to_loguru(logger)
# Later: remove the returned handler from logging.getLogger("pyntral").
```

Loguru is optional; it should be configured by the host application. The adapter forwards stdlib log records without installing a handler on the global root logger.

## Privacy and request correlation

Requests receive `X-Request-ID`; event records may contain the same correlation ID. Pyntral avoids logging request bodies and full query strings. `LoggingConfig.include_principal_id` and `include_record_id` are off by default. Avoid sending private payloads through `Admin.log_event` custom fields; logging sinks do not enforce database field ACLs.

`Admin.log_event("events", "myapp.task_dispatched", level="DEBUG", task_id="...")` uses the same channel policy. A `DEBUG` event is suppressed unless both logger and configuration permit it. For operations generating high volume, use channel and event filters rather than disabling all error logs.
