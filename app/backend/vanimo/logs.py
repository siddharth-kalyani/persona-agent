"""Content-free logging (security invariant: logs carry IDs, codes and counts only).

Every log line goes through `_content_free`, which:
  * keeps only allow-listed keys, whose values are limited to plain numbers, booleans,
    or short identifier-like strings;
  * requires the event name to be a static identifier (``graph.call``), never free text;
  * replaces anything else with a count of dropped fields.

Libraries that log URLs or payloads (httpx, botocore, msal, uvicorn access logs) are
silenced below WARNING, and their messages are reduced to the logger name and level.
"""

from __future__ import annotations

import logging
import re
import sys
from typing import Any

import structlog

ALLOWED_KEYS = frozenset(
    {
        "event",
        "level",
        "timestamp",
        "logger",
        "request_id",
        "route",
        "method",
        "status",
        "duration_ms",
        "tenant_ref",
        "user_ref",
        "cell",
        "env",
        "error_code",
        "error_type",
        "graph_status",
        "graph_code",
        "attempt",
        "retry_after_s",
        "count",
        "model_id",
        "ttft_ms",
        "total_ms",
        "check",
        "outcome",
        "revision",
        "generator",
        "tier",
        "source",
        "stage",
    }
)

_SAFE_VALUE = re.compile(r"^[A-Za-z0-9_.:/{}\-]{0,128}$")
_EVENT = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)*$")


def _safe(value: Any) -> bool:
    if value is None or isinstance(value, bool | int | float):
        return True
    return isinstance(value, str) and bool(_SAFE_VALUE.match(value))


def _content_free(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    dropped = 0
    for key, value in event_dict.items():
        if key == "event":
            clean["event"] = value if isinstance(value, str) and _EVENT.match(value) else "invalid_event"
        elif key in ALLOWED_KEYS and _safe(value):
            clean[key] = value
        else:
            dropped += 1
    if dropped:
        clean["dropped_fields"] = dropped
    return clean


def _stdlib_content_free(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Third-party stdlib log records: keep logger name + level, never the message."""
    record = event_dict.pop("_record", None)
    event_dict.pop("_from_structlog", None)
    if record is not None and not record.name.startswith("vanimo"):
        return {
            "event": "lib.log",
            "logger": record.name,
            "level": record.levelname.lower(),
            "timestamp": event_dict.get("timestamp"),
        }
    return event_dict


class _StdoutHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """Writes to whatever sys.stdout is at emit time (works under test capture too)."""

    @property  # type: ignore[override]
    def stream(self) -> Any:
        return sys.stdout

    @stream.setter
    def stream(self, _: Any) -> None:
        pass


def configure_logging(level: str = "INFO", *, json: bool = True) -> None:
    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    renderer = structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer(colors=False)
    structlog.configure(
        processors=[*shared, _content_free, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        logger_factory=structlog.PrintLoggerFactory(),  # resolves sys.stdout per logger
        cache_logger_on_first_use=False,
    )

    # Route stdlib logging (uvicorn, httpx, botocore, msal) through the same filter.
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[_stdlib_content_free, _content_free, renderer],
    )
    handler = _StdoutHandler()
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for noisy in ("httpx", "httpcore", "botocore", "boto3", "urllib3", "msal", "anthropic", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    # We emit our own access log with the route template (never the raw path or query).
    logging.getLogger("uvicorn.access").disabled = True


def get_logger(name: str = "vanimo") -> structlog.typing.FilteringBoundLogger:
    return structlog.get_logger(name)
