"""Unit tests for standard logging configuration."""

from __future__ import annotations

import logging
from pathlib import Path

from src.cli import _configure_logging


def test_configure_logging_sets_json_formatter() -> None:
    log_path = _configure_logging("INFO", "json", Path("logs"))
    root = logging.getLogger()
    assert len(root.handlers) == 2
    assert log_path.name.startswith("nutanix-mcp-")
    assert log_path.suffix == ".log"
    formatter = root.handlers[0].formatter
    assert formatter is not None
    assert '"level":"%(levelname)s"' in formatter._fmt  # type: ignore[attr-defined]


def test_configure_logging_sets_text_formatter() -> None:
    _configure_logging("DEBUG", "text", Path("logs"))
    root = logging.getLogger()
    assert len(root.handlers) == 2
    assert root.level == logging.DEBUG
    formatter = root.handlers[0].formatter
    assert formatter is not None
    assert "%(levelname)s" in formatter._fmt  # type: ignore[attr-defined]
