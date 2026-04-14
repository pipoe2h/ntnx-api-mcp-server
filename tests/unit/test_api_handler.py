"""Unit tests for hardened GET execution handler behavior."""

from __future__ import annotations

from collections.abc import Callable

import httpx

from src.config import Settings
from src.handlers import APIHandler


def _settings() -> Settings:
    return Settings(
        pc_host="127.0.0.1",
        pc_port=9440,
        pc_username="admin",
        pc_password="secret",
    )


class _FakeResponse:
    def __init__(self, status_code: int, payload: object, headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {"content-type": "application/json"}

    def json(self) -> object:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    @property
    def text(self) -> str:
        return str(self._payload)


class _FakeClient:
    def __init__(self, get_impl: Callable[..., _FakeResponse]) -> None:
        self._get_impl = get_impl

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    def get(self, url: str, params: dict[str, str], headers: dict[str, str]) -> _FakeResponse:
        return self._get_impl(url=url, params=params, headers=headers)


def test_resolve_path_requires_exact_path_params() -> None:
    handler = APIHandler(_settings())
    assert handler._resolve_path("/vms/{vmId}", {"vmId": "a/b"}) == "/vms/a%2Fb"

    try:
        handler._resolve_path("/vms/{vmId}", {})
        raise AssertionError("Expected missing path param error")
    except ValueError as exc:
        assert "Missing required path parameters" in str(exc)

    try:
        handler._resolve_path("/vms/{vmId}", {"vmId": "1", "extra": "x"})
        raise AssertionError("Expected unexpected path param error")
    except ValueError as exc:
        assert "Unexpected path parameters" in str(exc)


def test_execute_get_request_returns_deterministic_http_error(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def _get_impl(**kwargs):  # type: ignore[no-untyped-def]
        return _FakeResponse(
            status_code=503,
            payload={
                "metadata": {"messages": [{"message": "failure"}]},
                "data": {"error": [{"message": "temporary"}]},
            },
        )

    monkeypatch.setattr(
        "src.handlers.api_handler.httpx.Client",
        lambda **_kwargs: _FakeClient(_get_impl),
    )

    result = APIHandler(_settings()).execute_get_request(
        path="/vms/{vmId}",
        path_params={"vmId": "123"},
        query_params={"$limit": 10, "$expand": ["nic", "disk"], "skipNone": None},
    )

    assert "metadata" in result
    assert "data" in result
    assert result["data"]["error"][0]["message"] == "temporary"


def test_execute_get_request_maps_timeout_error(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def _get_impl(**kwargs):  # type: ignore[no-untyped-def]
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(
        "src.handlers.api_handler.httpx.Client",
        lambda **_kwargs: _FakeClient(_get_impl),
    )

    try:
        APIHandler(_settings()).execute_get_request(
            path="/clusters",
            path_params={},
            query_params={},
        )
        raise AssertionError("Expected timeout exception")
    except httpx.ReadTimeout:
        pass
