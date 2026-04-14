"""Unit tests for structured logging helpers."""

from __future__ import annotations

import json
import logging

from src.utils import JsonLogFormatter, log_event


def test_json_formatter_outputs_event_fields() -> None:
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="sample message",
        args=(),
        exc_info=None,
    )
    setattr(record, "extra_payload", {"event": "sample_event", "foo": "bar"})
    formatted = formatter.format(record)
    parsed = json.loads(formatted)
    assert parsed["logger"] == "test.logger"
    assert parsed["event"] == "sample_event"
    assert parsed["foo"] == "bar"


def test_log_event_sets_structured_payload(caplog) -> None:  # type: ignore[no-untyped-def]
    logger = logging.getLogger("test.log_event")
    with caplog.at_level(logging.INFO, logger="test.log_event"):
        log_event(logger, logging.INFO, "runtime_event", key="value")
    assert len(caplog.records) == 1
    payload = getattr(caplog.records[0], "extra_payload")
    assert payload["event"] == "runtime_event"
    assert payload["key"] == "value"
