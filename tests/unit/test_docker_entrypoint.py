"""Tests for the container entrypoint's command normalization."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess


ENTRYPOINT = Path(__file__).parents[2] / "docker-entrypoint.sh"


def _run_entrypoint_calls(
    tmp_path: Path,
    *arguments: str,
    artifacts_available: bool = True,
) -> list[list[str]]:
    bin_dir = tmp_path / "bin"
    artifacts_dir = tmp_path / "artifacts"
    bin_dir.mkdir()
    artifacts_dir.mkdir()
    if artifacts_available:
        (artifacts_dir / "test-all-documentation.yaml").touch()

    executable = bin_dir / "nutanix-mcp"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "print(json.dumps(sys.argv[1:]))\n"
    )
    executable.chmod(0o755)

    environment = os.environ | {
        "ARTIFACTS_DIR": str(artifacts_dir),
        "LOG_DIR": str(tmp_path / "logs"),
        "MCP_PORT": "8765",
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
    }
    result = subprocess.run(
        [str(ENTRYPOINT), *arguments],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return [json.loads(line) for line in result.stdout.splitlines()]


def _run_entrypoint(tmp_path: Path, *arguments: str) -> list[str]:
    return _run_entrypoint_calls(tmp_path, *arguments)[-1]


def test_option_only_arguments_restore_default_http_command(tmp_path: Path) -> None:
    arguments = _run_entrypoint(tmp_path, "--pc-host", "10.54.116.7")

    assert arguments == [
        "serve-http",
        "--pc-host",
        "10.54.116.7",
        "--host",
        "0.0.0.0",
        "--port",
        "8765",
    ]


def test_option_only_arguments_preserve_pc_insecure(tmp_path: Path) -> None:
    arguments = _run_entrypoint(tmp_path, "--pc-insecure", "true")

    assert arguments[1:3] == ["--pc-insecure", "true"]


def test_automatic_initialization_receives_pc_insecure(tmp_path: Path) -> None:
    calls = _run_entrypoint_calls(
        tmp_path,
        "--pc-insecure",
        "true",
        artifacts_available=False,
    )

    assert calls[0] == ["init", "--pc-insecure", "true"]
    assert calls[1][1:3] == ["--pc-insecure", "true"]


def test_combined_option_and_value_are_normalized(tmp_path: Path) -> None:
    arguments = _run_entrypoint(
        tmp_path,
        "--pc-host 10.54.116.7",
        "--pc-password a password with spaces",
    )

    assert arguments[1:5] == [
        "--pc-host",
        "10.54.116.7",
        "--pc-password",
        "a password with spaces",
    ]


def test_explicit_http_bind_options_are_preserved(tmp_path: Path) -> None:
    arguments = _run_entrypoint(
        tmp_path,
        "serve-http",
        "--host",
        "127.0.0.1",
        "--port=9000",
    )

    assert arguments == ["serve-http", "--host", "127.0.0.1", "--port=9000"]
