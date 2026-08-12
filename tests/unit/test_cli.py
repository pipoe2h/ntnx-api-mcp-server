"""Unit tests for CLI configuration persistence."""

from __future__ import annotations

import errno
import logging
from pathlib import Path
from unittest.mock import MagicMock

from src.cli import _save_config_dotenv
from src.config import Settings


def test_save_config_dotenv_writes_resolved_settings(tmp_path: Path) -> None:
    target_file = tmp_path / ".env"

    saved = _save_config_dotenv(Settings(pc_host="pc.example.test"), target_file)

    assert saved is True
    assert "PC_HOST=pc.example.test" in target_file.read_text(encoding="utf-8")


def test_save_config_dotenv_skips_read_only_filesystem(caplog) -> None:  # type: ignore[no-untyped-def]
    target_file = MagicMock(spec=Path)
    target_file.__str__.return_value = ".env"
    target_file.write_text.side_effect = OSError(
        errno.EROFS,
        "Read-only file system",
        ".env",
    )

    with caplog.at_level(logging.WARNING, logger="src.cli"):
        saved = _save_config_dotenv(Settings(), target_file)

    assert saved is False
    assert "event=config_dotenv_save_skipped" in caplog.text
    assert "Read-only file system" in caplog.text
