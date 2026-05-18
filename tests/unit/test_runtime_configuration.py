"""Unit tests for runtime configuration precedence and mode behavior."""

from __future__ import annotations

from pathlib import Path

from src.config import load_settings


def test_load_settings_precedence_env_then_file_then_cli(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("PC_PORT", "9440")
    monkeypatch.setenv("PC_INSECURE", "true")
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "\n".join(
            [
                "pc_port: 9441",
                "log_level: WARNING",
                "pc_insecure: false",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(
        config_file=config_file,
        overrides={"pc_port": 9442, "log_level": "ERROR"},
    )

    assert settings.pc_port == 9442
    assert settings.log_level == "ERROR"
    assert settings.pc_insecure is False


def test_artifact_only_mode_allowed_without_pc_host() -> None:
    settings = load_settings(overrides={"pc_host": None})
    assert settings.pc_host is None
    # Access to runtime artifact paths should still be valid in artifact-only mode.
    assert settings.artifacts_dir.exists()
    assert settings.default_artifacts_dir.exists()
    assert settings.log_dir.exists()
