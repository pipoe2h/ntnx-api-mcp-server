"""Unit tests for standard logging configuration."""

from __future__ import annotations

import logging

from src.cli import _configure_logging


def test_configure_logging_sets_json_formatter() -> None:
    _configure_logging("INFO", "json")
    root = logging.getLogger()
    assert len(root.handlers) == 1
    formatter = root.handlers[0].formatter
    assert formatter is not None
    assert '"level":"%(levelname)s"' in formatter._fmt  # type: ignore[attr-defined]


def test_configure_logging_sets_text_formatter() -> None:
    _configure_logging("DEBUG", "text")
    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert root.level == logging.DEBUG
    formatter = root.handlers[0].formatter
    assert formatter is not None
    assert "%(levelname)s" in formatter._fmt  # type: ignore[attr-defined]
