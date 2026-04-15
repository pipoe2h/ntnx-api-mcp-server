"""CLI entrypoint for init/refresh/run workflows."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from .auth import StartupValidationError, validate_startup_readiness
from .config import load_settings
from .server import build_runtime_dispatcher


LOGGER = logging.getLogger(__name__)


def _save_config_dotenv(settings: Any, target_file: Path = Path(".env")) -> None:
    """Persist resolved runtime settings for repeatable local runs."""
    content = "\n".join(
        [
            f"PC_HOST={settings.pc_host or ''}",
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


def _configure_logging(log_level: str, log_format: str) -> None:
    """Configure standard-library logging handlers for CLI/runtime."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    if log_format == "json":
        formatter = (
            '{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s",'
            '"message":"%(message)s"}'
        )
    else:
        formatter = "%(asctime)s %(levelname)s %(name)s %(message)s"
    logging.basicConfig(level=level, format=formatter, force=True)


def main() -> None:
    """CLI entrypoint."""
    parser = _build_parser()
    args = parser.parse_args()

    settings = load_settings(
        config_file=args.config_file,
        overrides=_build_overrides(args),
    )
    _configure_logging(settings.log_level, settings.log_format)
    LOGGER.info(
        "event=cli_started command=%s log_level=%s log_format=%s",
        args.command or "run",
        settings.log_level,
        settings.log_format,
    )

    command = args.command or "run"

    if command == "init":
        from pull_from_developers_api import download_yamls

        if not settings.pc_host:
            print(
                json.dumps(
                    {
                        "mode": "init",
                        "error": "PC_HOST is required for init in connected mode.",
                    },
                    indent=2,
                )
            )
            raise SystemExit(1)

        summary = download_yamls(settings=settings, refresh=False, force=False)
        LOGGER.info(
            "event=init_completed discovered=%s processed=%s success=%s skipped=%s failed=%s duration_ms=%s",
            summary.discovered,
            summary.processed,
            summary.success,
            summary.skipped,
            summary.failed,
            summary.duration_ms,
        )
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

        if not settings.pc_host:
            print(
                json.dumps(
                    {
                        "mode": "refresh",
                        "error": "PC_HOST is required for refresh in connected mode.",
                    },
                    indent=2,
                )
            )
            raise SystemExit(1)

        summary = download_yamls(
            settings=settings,
            refresh=True,
            force=bool(getattr(args, "force", False)),
        )
        LOGGER.info(
            "event=refresh_completed discovered=%s processed=%s success=%s skipped=%s failed=%s deleted_artifacts=%s restored_artifacts=%s duration_ms=%s",
            summary.discovered,
            summary.processed,
            summary.success,
            summary.skipped,
            summary.failed,
            summary.deleted_artifacts,
            summary.restored_artifacts,
            summary.duration_ms,
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

    if settings.pc_host:
        try:
            readiness = validate_startup_readiness(settings)
            startup_ready = readiness.ok
            startup_mode = "connected"
            startup_probe_skipped = False
            startup_warning = None
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
    else:
        startup_ready = True
        startup_mode = "offline_artifact_mode"
        startup_probe_skipped = True
        startup_warning = (
            "PC_HOST is not configured. Running in artifact-only mode; "
            "API execution calls require a configured Prism Central host."
        )

    dispatcher = build_runtime_dispatcher(settings)
    load_result = dispatcher.load_result
    tools = dispatcher.list_tools()
    LOGGER.info(
        "event=run_started startup_mode=%s startup_probe_skipped=%s artifacts_source=%s operation_count=%s registered_tool_count=%s",
        startup_mode,
        startup_probe_skipped,
        load_result.artifacts_source,
        len(load_result.operations),
        len(tools),
    )
    print(
        json.dumps(
            {
                "mode": "run",
                "startup_ready": startup_ready,
                "startup_mode": startup_mode,
                "startup_probe_skipped": startup_probe_skipped,
                "startup_warning": startup_warning,
                "artifacts_source": load_result.artifacts_source,
                "artifact_directory": str(load_result.artifact_directory),
                "artifact_files": [str(path) for path in load_result.files],
                "operation_count": len(load_result.operations),
                "namespace_tool_count": len(load_result.namespace_tools),
                "discovery_tool_count": len(load_result.discovery_tools),
                "registered_tool_count": len(tools),
            },
            indent=2,
        )
    )
