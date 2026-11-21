"""Application-owned observability; never install handlers on the host root logger.

The package emits structured stdlib logging records under ``pyntral.*``.
Host applications choose their own sinks (including Loguru) and filters.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock
from typing import Any, IO, Mapping

CHANNELS = frozenset({"auth", "security", "resource", "action", "bridge", "http", "lifecycle", "events"})
LEVELS = {"TRACE": 5, "DEBUG": logging.DEBUG, "INFO": logging.INFO,
          "WARNING": logging.WARNING, "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL,
          "OFF": 100}
DEFAULT_CHANNELS = {"auth": "INFO", "security": "WARNING", "resource": "INFO",
                    "action": "INFO", "bridge": "WARNING", "http": "INFO", "lifecycle": "INFO", "events": "INFO"}
logging.addLevelName(5, "TRACE")
request_id_var: ContextVar[str | None] = ContextVar("pyntral_request_id", default=None)


# A library must not produce console output unless its user explicitly configures it.
_root = logging.getLogger("pyntral")
if not _root.handlers:
    _root.addHandler(logging.NullHandler())


def _level(value: str) -> int:
    if not isinstance(value, str) or value.upper() not in LEVELS:
        raise ValueError(f"Invalid log level {value!r}; choose {', '.join(LEVELS)}")
    return LEVELS[value.upper()]


@dataclass(slots=True)
class LoggingConfig:
    """Event policy of one Admin instance, independent of global logging handlers.

    ``http`` controls *admin middleware events*, not Uvicorn's access logger.
    Uvicorn's access logger is configured separately (CLI: --access-log).
    """

    level: str = "INFO"
    channels: dict[str, str] = field(default_factory=dict)
    events: dict[str, bool] = field(default_factory=dict)
    http: str = "errors"  # off | errors | slow | all
    slow_request_ms: float = 750.0
    include_principal_id: bool = False
    include_record_id: bool = False

    def __post_init__(self) -> None:
        self.level = self.level.upper()
        _level(self.level)
        if self.http not in ("off", "errors", "slow", "all"):
            raise ValueError("LoggingConfig.http must be off, errors, slow or all")
        if self.slow_request_ms < 0:
            raise ValueError("slow_request_ms must be >= 0")
        for name, level in self.channels.items():
            if name not in CHANNELS:
                raise ValueError(f"Unknown logging channel: {name}")
            _level(level)
        if any(not isinstance(k, str) or not isinstance(v, bool) for k, v in self.events.items()):
            raise ValueError("LoggingConfig.events must map event names to bool")

    def enabled(self, channel: str, event: str, level: str) -> bool:
        if channel not in CHANNELS:
            raise ValueError(f"Unknown logging channel: {channel}")
        if self.events.get(event) is False:
            return False
        threshold = (_level(self.channels[channel]) if channel in self.channels else
                     max(_level(self.level), _level(DEFAULT_CHANNELS[channel])))
        return _level(level) >= threshold

    @classmethod
    def from_environment(cls) -> LoggingConfig:
        """CLI-only configuration; does not automatically read unrelated host env vars."""
        raw = os.getenv("PYNTRAL_LOG_CHANNELS", "")
        overrides: dict[str, str] = {}
        for pair in raw.split(","):
            if pair.strip():
                name, separator, value = pair.partition("=")
                if not separator:
                    raise ValueError(f"Invalid channel override: {pair}")
                overrides[name.strip()] = value.strip().upper()
        event_settings: dict[str, bool] = {}
        for pair in os.getenv("PYNTRAL_LOG_EVENTS", "").split(","):
            if pair.strip():
                name, separator, value = pair.partition("=")
                if not separator or value.strip().upper() not in ("ON", "OFF"):
                    raise ValueError(f"Invalid event override: {pair}")
                event_settings[name.strip()] = value.strip().upper() == "ON"
        return cls(
            events=event_settings,
            level=os.getenv("PYNTRAL_LOG_LEVEL", "INFO"),
            channels=overrides,
            http=os.getenv("PYNTRAL_LOG_HTTP", "errors"),
            slow_request_ms=float(os.getenv("PYNTRAL_SLOW_REQUEST_MS", "750")),
        )


def emit(config: LoggingConfig, channel: str, event: str, *, level: str = "INFO",
         **fields: Any) -> None:
    """Emit only safe metadata; callers must not pass request bodies or query strings."""
    if not config.enabled(channel, event, level):
        return
    logger = logging.getLogger(f"pyntral.{channel}")
    numeric_level = _level(level)
    if not logger.isEnabledFor(numeric_level):
        return
    request_id = request_id_var.get()
    details = {key: value for key, value in fields.items() if value is not None}
    if request_id:
        details["request_id"] = request_id
    logger.log(numeric_level, event, extra={"admin_event": event, "admin_fields": details})


class EventFormatter(logging.Formatter):
    """Compact or JSON output with safe structured fields and no URL query strings."""

    def __init__(self, *, json_lines: bool = False, template: str | None = None):
        super().__init__()
        self.json_lines = json_lines
        self.template = template or "{time} | {level:<7} | {channel} | {event}{details}"

    def format(self, record: logging.LogRecord) -> str:
        fields = getattr(record, "admin_fields", {})
        event = getattr(record, "admin_event", record.getMessage())
        time = datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds")
        if self.json_lines:
            return json.dumps({"timestamp": time, "level": record.levelname,
                               "channel": record.name, "event": event, **fields},
                              ensure_ascii=False, default=str)
        details = "".join(f" {k}={str(v)!r}" for k, v in fields.items())
        return self.template.format(time=time, level=record.levelname,
                                    channel=record.name, event=event, details=details)


# One package-level handler is sufficient; replacing only ours avoids duplicates on reload.
_MANAGED_HANDLERS: list[tuple[logging.Logger, logging.Handler]] = []
_HANDLER_LOCK = Lock()
_PREVIOUS_LEVEL: int | None = None


def configure_logging(*, level: str = "INFO", format: str = "compact",
                      file: str | Path | None = None, console: bool = True,
                      template: str | None = None, stream: IO[str] | None = None,
                      formatter: logging.Formatter | None = None,
                      channel_files: Mapping[str, str | Path] | None = None,
                      max_bytes: int = 10_000_000, backup_count: int = 3) -> None:
    """Opt-in console/file logging for pyntral only; never alter root/Uvicorn.

    Use the host app's regular logging configuration instead if preferred.
    Calling this function again replaces only handlers installed by this function.
    """
    if format not in ("compact", "json"):
        raise ValueError("format must be compact or json")
    if max_bytes < 1 or backup_count < 0:
        raise ValueError("max_bytes must be positive and backup_count nonnegative")
    for channel in (channel_files or {}):
        if channel not in CHANNELS:
            raise ValueError(f"Unknown log channel for file sink: {channel}")
    numeric_level = _level(level)
    if numeric_level == LEVELS["OFF"]:
        numeric_level = logging.CRITICAL + 1
    if template and format == "json":
        raise ValueError("template is only available with compact format")
    fmt = formatter or EventFormatter(json_lines=(format == "json"), template=template)

    class _ManualLogFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return hasattr(record, "admin_event") or record.levelno >= numeric_level
    new_handlers: list[tuple[logging.Logger, logging.Handler]] = []
    try:
        if console:
            h = logging.StreamHandler(stream or sys.stderr)
            h.setFormatter(fmt)
            h.addFilter(_ManualLogFilter())
            new_handlers.append((_root, h))
        if file is not None:
            file_path = Path(file)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            h = RotatingFileHandler(file_path, maxBytes=max_bytes, backupCount=backup_count,
                                    encoding="utf-8")
            h.setFormatter(fmt)
            h.addFilter(_ManualLogFilter())
            new_handlers.append((_root, h))
        for channel, destination in (channel_files or {}).items():
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)
            h = RotatingFileHandler(path, maxBytes=max_bytes, backupCount=backup_count,
                                    encoding="utf-8")
            h.setFormatter(fmt)
            h.addFilter(_ManualLogFilter())
            new_handlers.append((logging.getLogger(f"pyntral.{channel}"), h))
    except Exception:
        for _, handler in new_handlers:
            handler.close()
        raise
    global _PREVIOUS_LEVEL
    with _HANDLER_LOCK:
        if _PREVIOUS_LEVEL is None:
            _PREVIOUS_LEVEL = _root.level
        for logger, handler in _MANAGED_HANDLERS:
            logger.removeHandler(handler)
            handler.close()
        _MANAGED_HANDLERS[:] = new_handlers
        for logger, handler in new_handlers:
            logger.addHandler(handler)
        _root.setLevel(LEVELS["TRACE"])


def stop_logging() -> None:
    """Remove only handlers installed by configure_logging."""
    global _PREVIOUS_LEVEL
    with _HANDLER_LOCK:
        for logger, handler in _MANAGED_HANDLERS:
            logger.removeHandler(handler)
            handler.close()
        _MANAGED_HANDLERS.clear()
        if _PREVIOUS_LEVEL is not None:
            _root.setLevel(_PREVIOUS_LEVEL)
            _PREVIOUS_LEVEL = None


class LoguruHandler(logging.Handler):
    """Forward only pyntral records into an *existing* Loguru instance."""

    def __init__(self, target: Any):
        super().__init__()
        self.target = target

    def emit(self, record: logging.LogRecord) -> None:
        details = dict(getattr(record, "admin_fields", {}))
        details.update(event=getattr(record, "admin_event", record.getMessage()),
                       channel=record.name)
        try:
            self.target.bind(**details).opt(exception=record.exc_info).log(
                record.levelname, record.getMessage())
        except Exception:
            self.handleError(record)


def forward_to_loguru(target: Any) -> logging.Handler:
    """Attach a Loguru sink without changing its global sinks or stdlib root logger.

    The returned handler can be removed with ``logging.getLogger('pyntral').removeHandler(handler)``.
    """
    handler = LoguruHandler(target)
    _root.addHandler(handler)
    # A library logger should let the host's logging level control output.
    _root.setLevel(logging.DEBUG)
    return handler
