"""Application settings and startup validation."""

from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path
from typing import Any, Literal, Mapping

import yaml
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .constants import (
    DEFAULT_STARTUP_RETRY_ATTEMPTS,
    DEFAULT_STARTUP_TIMEOUT_SECONDS,
    DEVELOPERS_NAMESPACE_LIST_URL,
)


class Settings(BaseSettings):
    """Runtime configuration for the MCP server."""

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Prism Central connection
    pc_host: str | None = Field(default=None, description="Prism Central host (IP or FQDN)")
    pc_port: int = Field(default=9440, description="Prism Central API port")
    pc_username: str | None = Field(default=None, description="Prism Central username")
    pc_password: SecretStr | None = Field(default=None, description="Prism Central password")
    pc_api_key: SecretStr | None = Field(default=None, description="Prism Central API key")
    pc_insecure: bool = Field(
        default=False,
        description="Skip TLS certificate verification (default: False — enforce TLS)",
    )

    # Runtime locations
    artifacts_dir: Path | None = Field(default=None, description="Runtime artifacts directory")
    default_artifacts_dir: Path | None = Field(
        default=None, description="Bundled fallback specs directory"
    )

    # Namespace discovery / fetching
    namespace_source_url: str = Field(
        default=DEVELOPERS_NAMESPACE_LIST_URL, description="Namespace discovery endpoint"
    )
    namespace_override_list: str | None = Field(
        default=None,
        description="Comma-separated namespace override list for restricted environments",
    )

    # Runtime controls
    read_only_mode: bool = Field(
        default=True,
        description="When true, reject all non-GET operations before they reach Prism Central",
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["text", "json"] = "text"
    log_dir: Path | None = Field(default=None, description="Directory for per-restart log files")

    @property
    def project_root(self) -> Path:
        """Repository root directory."""
        return Path(__file__).resolve().parents[2]

    @property
    def pc_base_url(self) -> str:
        """Base API URL for Prism Central."""
        if not self.pc_host:
            raise ValueError("PC_HOST is required to build Prism Central base URL.")
        scheme = "https" if self.pc_port == 9440 else "http"
        return f"{scheme}://{self.pc_host}:{self.pc_port}/api"

    @property
    def startup_timeout_seconds(self) -> float:
        """Internal startup probe timeout."""
        return DEFAULT_STARTUP_TIMEOUT_SECONDS

    @property
    def startup_retry_attempts(self) -> int:
        """Internal startup probe retry count."""
        return DEFAULT_STARTUP_RETRY_ATTEMPTS

    @property
    def namespace_overrides(self) -> list[str]:
        """Optional list of namespace overrides."""
        if not self.namespace_override_list:
            return []
        return [
            value.strip()
            for value in self.namespace_override_list.split(",")
            if value.strip()
        ]

    @model_validator(mode="after")
    def validate_paths(self) -> "Settings":
        """Ensure runtime and fallback artifact directories are usable."""
        if self.artifacts_dir is None:
            self.artifacts_dir = self.project_root / "artifacts"
        if self.default_artifacts_dir is None:
            self.default_artifacts_dir = self.project_root / "src" / "artifacts" / "default_specs"
        if self.log_dir is None:
            self.log_dir = self.project_root / "logs"

        try:
            self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError as exc:
            # Migration guardrail: old container-style /app paths should not block local startup.
            if str(self.artifacts_dir).startswith("/app/"):
                self.artifacts_dir = self.project_root / "artifacts"
                self.artifacts_dir.mkdir(parents=True, exist_ok=True)
            else:
                raise ValueError(
                    f"Artifacts directory is not writable: {self.artifacts_dir}"
                ) from exc
        if not self.default_artifacts_dir.exists():
            self.default_artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        if not self.default_artifacts_dir.is_dir():
            raise ValueError(
                f"Bundled default specs path is not a directory: {self.default_artifacts_dir}"
            )
        if not self.log_dir.is_dir():
            raise ValueError(f"Log directory is not a directory: {self.log_dir}")
        return self


_SETTINGS: Settings | None = None


def _load_settings_file(config_file: Path) -> dict[str, Any]:
    """Load settings from a JSON, YAML, or TOML file."""
    if not config_file.exists():
        raise ValueError(f"Settings file does not exist: {config_file}")
    if not config_file.is_file():
        raise ValueError(f"Settings path is not a file: {config_file}")

    suffix = config_file.suffix.lower()
    with config_file.open("rb") as file_handle:
        content = file_handle.read().decode("utf-8")
    if suffix == ".json":
        loaded_json = json.loads(content)
        return loaded_json if isinstance(loaded_json, dict) else {}
    if suffix in {".yaml", ".yml"}:
        loaded_yaml = yaml.safe_load(content)
        return loaded_yaml if isinstance(loaded_yaml, dict) else {}
    if suffix == ".toml":
        loaded_toml = tomllib.loads(content)
        return loaded_toml if isinstance(loaded_toml, dict) else {}

    raise ValueError("Unsupported settings file extension. Use .json, .yaml/.yml, or .toml.")


def _normalize_payload_keys(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize payload keys to snake_case settings names."""
    normalized: dict[str, Any] = {}
    for key, value in payload.items():
        normalized[key.lower()] = value
    return normalized


def _build_env_payload() -> dict[str, Any]:
    """Build environment payload from process env and `.env`."""
    env_keys = {
        "PC_HOST": "pc_host",
        "PC_PORT": "pc_port",
        "PC_USERNAME": "pc_username",
        "PC_PASSWORD": "pc_password",
        "PC_API_KEY": "pc_api_key",
        "PC_INSECURE": "pc_insecure",
        "ARTIFACTS_DIR": "artifacts_dir",
        "LOG_LEVEL": "log_level",
        "LOG_FORMAT": "log_format",
        "LOG_DIR": "log_dir",
        "NAMESPACE_SOURCE_URL": "namespace_source_url",
        "NAMESPACE_OVERRIDE_LIST": "namespace_override_list",
        "READ_ONLY_MODE": "read_only_mode",
    }
    env_payload: dict[str, Any] = {}
    for env_key, field_name in env_keys.items():
        if env_key in os.environ:
            env_payload[field_name] = os.environ[env_key]
    return env_payload


def load_settings(
    config_file: str | Path | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> Settings:
    """Build settings from environment, config-file, and CLI overrides."""
    merged_payload: dict[str, Any] = _build_env_payload()
    if config_file is not None:
        file_payload = _normalize_payload_keys(_load_settings_file(Path(config_file)))
        merged_payload.update(file_payload)
    merged_payload.update(_normalize_payload_keys(dict(overrides or {})))
    return Settings(**merged_payload)


def get_settings() -> Settings:
    """Return cached settings instance using default env/.env sources."""
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = load_settings()
    return _SETTINGS
