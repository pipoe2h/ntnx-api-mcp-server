"""Unit tests for CLI configuration persistence."""

from __future__ import annotations

import errno
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.cli import _build_overrides
from src.cli import _build_parser
from src.cli import _save_config_dotenv
from src.cli import _runtime_artifacts_available
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


def test_runtime_artifacts_available_requires_matching_yaml(tmp_path: Path) -> None:
    assert _runtime_artifacts_available(tmp_path) is False

    (tmp_path / "notes.yaml").write_text("not an artifact", encoding="utf-8")
    assert _runtime_artifacts_available(tmp_path) is False

    (tmp_path / "vmm-v4.2-all-documentation.yaml").write_text(
        "openapi: 3.0.0\npaths: {}\n",
        encoding="utf-8",
    )
    assert _runtime_artifacts_available(tmp_path) is True


def test_original_pc_arguments_are_accepted_after_command() -> None:
    args = _build_parser().parse_args(
        [
            "serve-http",
            "--pc-host",
            "pc.example.test",
            "--pc-port",
            "9441",
            "--pc-username",
            "admin",
            "--pc-password",
            "secret",
        ]
    )

    assert _build_overrides(args) == {
        "pc_host": "pc.example.test",
        "pc_port": 9441,
        "pc_username": "admin",
        "pc_password": "secret",
    }


def test_pc_arguments_accept_hyphens_before_command() -> None:
    args = _build_parser().parse_args(
        [
            "--pc-host",
            "pc.example.test",
            "--pc-username",
            "admin",
            "--pc-password",
            "secret",
            "serve-http",
        ]
    )

    overrides = _build_overrides(args)
    assert overrides["pc_host"] == "pc.example.test"
    assert overrides["pc_username"] == "admin"
    assert overrides["pc_password"] == "secret"
    assert "pc_port" not in overrides
    assert Settings(**overrides).pc_port == 9440


@pytest.mark.parametrize(
    ("value", "expected"),
    [("true", True), ("false", False)],
)
def test_pc_insecure_after_command_overrides_with_boolean(
    value: str,
    expected: bool,
) -> None:
    args = _build_parser().parse_args(["serve-http", "--pc-insecure", value])

    assert _build_overrides(args)["pc_insecure"] is expected


def test_pc_insecure_is_accepted_before_command() -> None:
    args = _build_parser().parse_args(["--pc-insecure", "true", "serve-http"])

    assert _build_overrides(args)["pc_insecure"] is True


def test_underscored_pc_argument_is_not_accepted() -> None:
    with pytest.raises(SystemExit) as exc_info:
        _build_parser().parse_args(["serve-http", "--pc_host", "pc.example.test"])

    assert exc_info.value.code == 2
