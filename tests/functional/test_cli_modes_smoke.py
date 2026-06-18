"""Functional smoke tests for CLI mode behavior."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import src.cli as cli_module
import src.pull_from_developers_api as pull_module


def _write_basic_yaml(target_file: Path) -> None:
    target_file.write_text(
        "\n".join(
            [
                "openapi: 3.0.0",
                "paths:",
                "  /vms:",
                "    get:",
                "      operationId: listVms",
                "      summary: List VMs",
            ]
        ),
        encoding="utf-8",
    )


def test_run_uses_offline_artifact_mode_without_pc_host(
    monkeypatch, capsys, tmp_path
) -> None:  # type: ignore[no-untyped-def]
    artifacts_dir = tmp_path / "artifacts"
    default_dir = tmp_path / "defaults"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    default_dir.mkdir(parents=True, exist_ok=True)
    _write_basic_yaml(default_dir / "vmm-v4.2-all-documentation.yaml")

    monkeypatch.setattr(cli_module, "_build_parser", lambda: _fake_args_for_run())
    monkeypatch.setattr(
        cli_module,
        "load_settings",
        lambda config_file, overrides: _fake_settings(
            pc_host=None,
            artifacts_dir=artifacts_dir,
            default_artifacts_dir=default_dir,
        ),
    )

    cli_module.main()
    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "run"
    assert output["startup_mode"] == "latest_release"
    assert output["startup_probe_skipped"] is True
    assert output["operation_count"] == 1


def test_init_works_without_pc_host_in_latest_release_mode(
    monkeypatch, capsys, tmp_path
) -> None:  # type: ignore[no-untyped-def]
    artifacts_dir = tmp_path / "artifacts"
    default_dir = tmp_path / "defaults"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    default_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(cli_module, "_build_parser", lambda: _fake_args_for_init())
    monkeypatch.setattr(
        cli_module,
        "load_settings",
        lambda config_file, overrides: _fake_settings(
            pc_host=None,
            artifacts_dir=artifacts_dir,
            default_artifacts_dir=default_dir,
        ),
    )

    @dataclass
    class _Summary:
        discovered: int = 1
        processed: int = 1
        success: int = 1
        skipped: int = 0
        not_available: int = 0
        failed: int = 0
        deleted_artifacts: int = 0
        restored_artifacts: int = 0
        duration_ms: int = 10
        artifact_mode: str = "latest_release"
        skipped_reasons: dict[str, int] | None = None
        not_available_reasons: dict[str, int] | None = None
        failed_reasons: dict[str, int] | None = None

    monkeypatch.setattr(
        pull_module,
        "download_yamls",
        lambda settings, refresh, force: _Summary(skipped_reasons={}, not_available_reasons={}, failed_reasons={}),
    )

    cli_module.main()
    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "init"
    assert output["artifact_mode"] == "latest_release"
    assert output["success"] == 1


class _FakeArgs:
    def __init__(self, command: str) -> None:
        self.command = command
        self.config_file = None
        self.pc_host = None
        self.pc_port = None
        self.pc_username = None
        self.pc_password = None
        self.pc_api_key = None
        self.pc_insecure = None
        self.log_level = None
        self.log_format = None
        self.log_dir = None
        self.namespace_source_url = None
        self.namespace_override_list = None
        self.force = False
        self.validate_only = False


class _FakeParser:
    def __init__(self, args: _FakeArgs) -> None:
        self.args = args

    def parse_args(self) -> _FakeArgs:
        return self.args


def _fake_args_for_run() -> _FakeParser:
    return _FakeParser(_FakeArgs(command="run"))


def _fake_args_for_init() -> _FakeParser:
    return _FakeParser(_FakeArgs(command="init"))


def _fake_settings(pc_host, artifacts_dir: Path, default_artifacts_dir: Path):  # type: ignore[no-untyped-def]
    from src.config import Settings

    return Settings(
        pc_host=pc_host,
        artifacts_dir=artifacts_dir,
        default_artifacts_dir=default_artifacts_dir,
    )
