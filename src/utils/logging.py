"""Structured logging helpers for runtime observability."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any


class JsonLogFormatter(logging.Formatter):
    """Render log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra_payload = getattr(record, "extra_payload", None)
        if isinstance(extra_payload, dict):
            payload.update(extra_payload)
        return json.dumps(payload, separators=(",", ":"))


def setup_logging(log_level: str, log_format: str) -> None:
    """Configure root logging once for CLI/runtime execution."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    handler = logging.StreamHandler()
    if log_format == "json":
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
    root.addHandler(handler)


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    """Emit a structured log event with key-value fields."""
    logger.log(
        level,
        event,
        extra={
            "extra_payload": {
                "event": event,
                **fields,
            }
        },
    )
