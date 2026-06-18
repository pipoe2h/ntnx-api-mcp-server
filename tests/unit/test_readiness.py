"""Unit tests for startup readiness validation."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from src.auth import (
    StartupAuthError,
    StartupConnectivityError,
    StartupValidationError,
    build_auth_context,
    validate_startup_readiness,
)
from src.config import Settings


def _settings() -> Settings:
    return Settings(pc_host="127.0.0.1", pc_port=9440, pc_username="admin", pc_password="secret")


def test_readiness_success(monkeypatch: pytest.MonkeyPatch) -> None:
    response = SimpleNamespace(status_code=200, is_error=False)
    monkeypatch.setattr("src.auth.readiness._probe_pc", lambda _settings: response)
    result = validate_startup_readiness(_settings())
    assert result.ok is True
    assert result.category == "ready"


def test_readiness_auth_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    response = SimpleNamespace(status_code=401, is_error=False)
    monkeypatch.setattr("src.auth.readiness._probe_pc", lambda _settings: response)
    with pytest.raises(StartupAuthError):
        validate_startup_readiness(_settings())


def test_readiness_endpoint_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    response = SimpleNamespace(status_code=404, is_error=False)
    monkeypatch.setattr("src.auth.readiness._probe_pc", lambda _settings: response)
    with pytest.raises(StartupValidationError):
        validate_startup_readiness(_settings())


def test_readiness_connectivity_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_connect_error(_settings: Settings) -> None:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("src.auth.readiness._probe_pc", _raise_connect_error)
    with pytest.raises(StartupConnectivityError):
        validate_startup_readiness(_settings())


def test_readiness_accepts_api_key_only(monkeypatch: pytest.MonkeyPatch) -> None:
    response = SimpleNamespace(status_code=200, is_error=False)
    monkeypatch.setattr("src.auth.readiness._probe_pc", lambda _settings: response)
    settings = Settings(
        pc_host="127.0.0.1", pc_port=9440, pc_api_key="key-1", pc_username=None, pc_password=None
    )
    result = validate_startup_readiness(settings)
    assert result.ok is True


def test_readiness_rejects_missing_all_auth() -> None:
    settings = Settings(pc_host="127.0.0.1", pc_port=9440, pc_username=None, pc_password=None, pc_api_key=None)
    with pytest.raises(StartupAuthError):
        validate_startup_readiness(settings)


def test_build_auth_context_api_key_wins_when_both_set() -> None:
    """API key takes priority over basic auth when both are configured."""
    settings = Settings(
        pc_host="127.0.0.1",
        pc_port=9440,
        pc_username="admin",
        pc_password="secret",
        pc_api_key="key-1",
    )
    auth, headers = build_auth_context(settings)
    assert auth is None  # basic auth suppressed
    assert headers["X-ntnx-api-key"] == "key-1"


def test_build_auth_context_api_key_only() -> None:
    settings = Settings(
        pc_host="127.0.0.1",
        pc_port=9440,
        pc_api_key="key-1",
        pc_username=None,
        pc_password=None,
    )
    auth, headers = build_auth_context(settings)
    assert auth is None
    assert headers["X-ntnx-api-key"] == "key-1"


def test_build_auth_context_basic_auth_only() -> None:
    settings = Settings(
        pc_host="127.0.0.1",
        pc_port=9440,
        pc_username="admin",
        pc_password="secret",
        pc_api_key=None,
    )
    auth, headers = build_auth_context(settings)
    assert auth == ("admin", "secret")
    assert "X-ntnx-api-key" not in headers
