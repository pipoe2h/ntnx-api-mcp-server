"""CLI entrypoint for init/refresh/run workflows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .auth import StartupValidationError, validate_startup_readiness
from .config import load_settings
from .server import load_operations_from_yamls


def _save_config_dotenv(settings: Any, target_file: Path = Path(".env")) -> None:
    """Persist resolved runtime settings for repeatable local runs."""
    content = "\n".join(
        [
            f"PC_HOST={settings.pc_host}",
            f"PC_PORT={settings.pc_port}",
            f"PC_USERNAME={settings.pc_username or ''}",
            f"PC_PASSWORD={settings.pc_password.get_secret_value() if settings.pc_password else ''}",
            f"PC_INSECURE={'true' if settings.pc_insecure else 'false'}",
            f"ARTIFACTS_DIR={settings.artifacts_dir}",
            f"LOG_LEVEL={settings.log_level}",
            "",
        ]
    )
    target_file.write_text(content, encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nutanix-mcp",
        description="Nutanix API MCP server",
    )
    parser.add_argument(
        "--config-file",
        help="Path to config file (.json/.yaml/.yml/.toml)",
    )
    parser.add_argument("--pc-host")
    parser.add_argument("--pc-port", type=int)
    parser.add_argument("--pc-username")
    parser.add_argument("--pc-password")
    parser.add_argument("--pc-insecure", choices=["true", "false"])
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    parser.add_argument("--log-format", choices=["text", "json"])
    parser.add_argument("--namespace-source-url")
    parser.add_argument("--namespace-override-list")

    subparsers = parser.add_subparsers(dest="command", required=False)
    subparsers.add_parser("init", help="Download YAMLs using namespace/version discovery")

    refresh_parser = subparsers.add_parser(
        "refresh",
        help="Refresh YAMLs by clearing and downloading latest",
    )
    refresh_parser.add_argument("--force", action="store_true")

    run_parser = subparsers.add_parser(
        "run",
        help="Run server startup YAML loading flow",
    )
    run_parser.add_argument("--validate-only", action="store_true")
    return parser


def _build_overrides(args: argparse.Namespace) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    if args.pc_host is not None:
        overrides["pc_host"] = args.pc_host
    if args.pc_port is not None:
        overrides["pc_port"] = args.pc_port
    if args.pc_username is not None:
        overrides["pc_username"] = args.pc_username
    if args.pc_password is not None:
        overrides["pc_password"] = args.pc_password
    if args.pc_insecure is not None:
        overrides["pc_insecure"] = args.pc_insecure == "true"
    if args.log_level is not None:
        overrides["log_level"] = args.log_level
    if args.log_format is not None:
        overrides["log_format"] = args.log_format
    if args.namespace_source_url is not None:
        overrides["namespace_source_url"] = args.namespace_source_url
    if args.namespace_override_list is not None:
        overrides["namespace_override_list"] = args.namespace_override_list
    return overrides


def main() -> None:
    """CLI entrypoint."""
    parser = _build_parser()
    args = parser.parse_args()

    settings = load_settings(
        config_file=args.config_file,
        overrides=_build_overrides(args),
    )

    command = args.command or "run"

    if command == "init":
        from pull_from_developers_api import download_yamls

        summary = download_yamls(settings=settings, refresh=False, force=False)
        _save_config_dotenv(settings)
        print(
            json.dumps(
                {
                    "mode": "init",
                    "discovered": summary.discovered,
                    "processed": summary.processed,
                    "success": summary.success,
                    "skipped": summary.skipped,
                    "failed": summary.failed,
                    "skipped_reasons": summary.skipped_reasons,
                    "failed_reasons": summary.failed_reasons,
                    "duration_ms": summary.duration_ms,
                },
                indent=2,
            )
        )
        return

    if command == "refresh":
        from pull_from_developers_api import download_yamls

        summary = download_yamls(
            settings=settings,
            refresh=True,
            force=bool(getattr(args, "force", False)),
        )
        _save_config_dotenv(settings)
        print(
            json.dumps(
                {
                    "mode": "refresh",
                    "discovered": summary.discovered,
                    "processed": summary.processed,
                    "success": summary.success,
                    "skipped": summary.skipped,
                    "failed": summary.failed,
                    "deleted_artifacts": summary.deleted_artifacts,
                    "restored_artifacts": summary.restored_artifacts,
                    "skipped_reasons": summary.skipped_reasons,
                    "failed_reasons": summary.failed_reasons,
                    "duration_ms": summary.duration_ms,
                },
                indent=2,
            )
        )
        return

    if bool(getattr(args, "validate_only", False)):
        result = {
            "pc_host": settings.pc_host,
            "pc_port": settings.pc_port,
            "pc_username": settings.pc_username,
            "pc_insecure": settings.pc_insecure,
            "log_level": settings.log_level,
            "log_format": settings.log_format,
            "artifacts_dir": str(settings.artifacts_dir),
            "default_artifacts_dir": str(settings.default_artifacts_dir),
        }
        print(json.dumps(result, indent=2))
        return

    try:
        readiness = validate_startup_readiness(settings)
    except StartupValidationError as exc:
        print(
            json.dumps(
                {
                    "mode": "run",
                    "startup_ready": False,
                    "error": str(exc),
                },
                indent=2,
            )
        )
        raise SystemExit(1) from exc

    load_result = load_operations_from_yamls(settings)
    print(
        json.dumps(
            {
                "mode": "run",
                "startup_ready": readiness.ok,
                "artifacts_source": load_result.artifacts_source,
                "artifact_directory": str(load_result.artifact_directory),
                "artifact_files": [str(path) for path in load_result.files],
                "operation_count": len(load_result.operations),
                "namespace_tool_count": len(load_result.namespace_tools),
                "discovery_tool_count": len(load_result.discovery_tools),
            },
            indent=2,
        )
    )
