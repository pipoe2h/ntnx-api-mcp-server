"""Unit tests for startup readiness validation."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from src.auth import (
    StartupAuthError,
    StartupConnectivityError,
    StartupValidationError,
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
