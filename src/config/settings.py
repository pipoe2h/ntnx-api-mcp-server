"""Application settings and startup validation."""

from __future__ import annotations

import os
import json
from pathlib import Path
import tomllib
from typing import Any, Literal, Mapping

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml

from .constants import (
    DEFAULT_STARTUP_RETRY_ATTEMPTS,
    DEFAULT_STARTUP_TIMEOUT_SECONDS,
)


class Settings(BaseSettings):
    """Runtime configuration for the MCP server."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Prism Central basic auth configuration (required)
    pc_host: str = Field(..., description="Prism Central host (IP or FQDN)")
    pc_port: int = Field(..., description="Prism Central API port")
    pc_username: str = Field(..., description="Prism Central username")
    pc_password: SecretStr = Field(..., description="Prism Central password")
    pc_insecure: bool = Field(default=True, description="Skip TLS certificate verification")

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["text", "json"] = "text"

    @property
    def project_root(self) -> Path:
        """Repository root directory."""
        return Path(__file__).resolve().parents[2]

    @property
    def artifacts_dir(self) -> Path:
        """Internally controlled runtime artifacts directory."""
        return self.project_root / "artifacts"

    @property
    def default_artifacts_dir(self) -> Path:
        """Internally controlled bundled default specs directory."""
        return self.project_root / "src" / "artifacts" / "default_specs"

    @property
    def pc_base_url(self) -> str:
        """Base API URL for Prism Central."""
        return f"https://{self.pc_host}:{self.pc_port}/api"

    @property
    def startup_timeout_seconds(self) -> float:
        """Internal startup probe timeout (not user configurable)."""
        return DEFAULT_STARTUP_TIMEOUT_SECONDS

    @property
    def startup_retry_attempts(self) -> int:
        """Internal startup probe retry count (not user configurable)."""
        return DEFAULT_STARTUP_RETRY_ATTEMPTS

    @model_validator(mode="after")
    def validate_paths(self) -> "Settings":
        """Ensure internal directories are present and usable."""
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        if not self.default_artifacts_dir.exists():
            raise ValueError(
                f"Bundled default specs directory is missing: {self.default_artifacts_dir}"
            )
        if not self.default_artifacts_dir.is_dir():
            raise ValueError(
                f"Bundled default specs path is not a directory: {self.default_artifacts_dir}"
            )
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
        if suffix == ".json":
            return json.loads(file_handle.read().decode("utf-8"))
        if suffix in {".yaml", ".yml"}:
            loaded_yaml = yaml.safe_load(file_handle.read().decode("utf-8"))
            return loaded_yaml if isinstance(loaded_yaml, dict) else {}
        if suffix == ".toml":
            loaded_toml = tomllib.loads(file_handle.read().decode("utf-8"))
            return loaded_toml if isinstance(loaded_toml, dict) else {}

    raise ValueError(
        "Unsupported settings file extension. Use .json, .yaml/.yml, or .toml."
    )


def _normalize_payload_keys(payload: Mapping[str, Any]) -> dict[str, Any]:
    """
    Normalize payload keys to Settings field names.

    This allows config files and future CLI layers to use either:
    - snake_case: pc_host
    - env-style: PC_HOST
    """
    normalized: dict[str, Any] = {}
    for key, value in payload.items():
        key_name = key.lower()
        normalized[key_name] = value
    return normalized


def _build_env_payload() -> dict[str, Any]:
    """
    Build environment payload from process env.

    `.env` loading is handled by BaseSettings via model_config.
    This helper exists only to make precedence explicit in load_settings.
    """
    env_keys = {
        "PC_HOST": "pc_host",
        "PC_PORT": "pc_port",
        "PC_USERNAME": "pc_username",
        "PC_PASSWORD": "pc_password",
        "PC_INSECURE": "pc_insecure",
        "LOG_LEVEL": "log_level",
        "LOG_FORMAT": "log_format",
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
    """
    Build settings from layered sources.

    Precedence (lowest -> highest):
    1. `.env` and process environment
    2. Optional settings file payload
    3. Optional explicit overrides (CLI)
    """
    # Start with env-derived values (includes docker orchestration use case).
    # BaseSettings still reads env/.env, but we make the merge explicit so file and
    # override precedence is deterministic and easy to reason about.
    merged_payload: dict[str, Any] = _build_env_payload()

    if config_file is not None:
        file_payload = _normalize_payload_keys(_load_settings_file(Path(config_file)))
        merged_payload.update(file_payload)

    override_payload = _normalize_payload_keys(dict(overrides or {}))
    merged_payload.update(override_payload)
    return Settings(**merged_payload)


def get_settings() -> Settings:
    """Return cached settings instance using default env/.env sources."""
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = load_settings()
    return _SETTINGS
