"""CLI entrypoint for MCP server configuration loading."""

from __future__ import annotations

import argparse
import json
from typing import Any

from .config import load_settings


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
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate configuration and exit",
    )
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
    return overrides


def main() -> None:
    """CLI entrypoint."""
    parser = _build_parser()
    args = parser.parse_args()

    settings = load_settings(
        config_file=args.config_file,
        overrides=_build_overrides(args),
    )

    if args.validate_only:
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

    # Runtime wiring will be added in a later PR.
    print("Configuration loaded successfully.")
