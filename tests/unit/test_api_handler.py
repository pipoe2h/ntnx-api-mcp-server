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
    def __init__(self, request_impl: Callable[..., _FakeResponse]) -> None:
        self._request_impl = request_impl

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    def request(
        self,
        method: str,
        url: str,
        params: dict[str, str],
        headers: dict[str, str],
        json: dict[str, object] | None = None,
    ) -> _FakeResponse:
        return self._request_impl(method=method, url=url, params=params, headers=headers, json=json)


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
    def _request_impl(**kwargs):  # type: ignore[no-untyped-def]
        assert kwargs["method"] == "GET"
        return _FakeResponse(
            status_code=503,
            payload={
                "metadata": {"messages": [{"message": "failure"}]},
                "data": {"error": [{"message": "temporary"}]},
            },
        )

    monkeypatch.setattr(
        "src.handlers.api_handler.httpx.Client",
        lambda **_kwargs: _FakeClient(_request_impl),
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
    def _request_impl(**kwargs):  # type: ignore[no-untyped-def]
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(
        "src.handlers.api_handler.httpx.Client",
        lambda **_kwargs: _FakeClient(_request_impl),
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


def test_execute_request_supports_body_and_api_key_header(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    settings = Settings(
        pc_host="127.0.0.1",
        pc_port=9440,
        pc_api_key="api-key-123",
        pc_username=None,
        pc_password=None,
    )
    captured: dict[str, object] = {}

    def _request_impl(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return _FakeResponse(status_code=200, payload={"data": {"ok": True}})

    monkeypatch.setattr(
        "src.handlers.api_handler.httpx.Client",
        lambda **_kwargs: _FakeClient(_request_impl),
    )

    result = APIHandler(settings).execute_request(
        method="POST",
        path="/vms",
        path_params={},
        query_params={"$limit": 10},
        headers={"X-Custom": "yes"},
        body={"name": "vm-1"},
    )

    assert result["data"]["ok"] is True
    assert captured["method"] == "POST"
    assert captured["json"] == {"name": "vm-1"}
    sent_headers = captured["headers"]
    assert isinstance(sent_headers, dict)
    assert sent_headers["X-ntnx-api-key"] == "api-key-123"
    assert sent_headers["X-Custom"] == "yes"
    assert sent_headers["X-NTNX-REQUEST-SOURCE"] == "MCP"


def test_execute_request_sanitizes_401(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def _request_impl(**kwargs):  # type: ignore[no-untyped-def]
        return _FakeResponse(
            status_code=401,
            payload={"message": "Unauthorized", "realm": "prism", "token": "secret123"},
        )

    monkeypatch.setattr(
        "src.handlers.api_handler.httpx.Client",
        lambda **_kwargs: _FakeClient(_request_impl),
    )

    result = APIHandler(_settings()).execute_get_request(path="/vms", path_params={})

    assert "error" in result
    assert "Authentication failed" in result["error"]
    assert "secret123" not in str(result)
    assert "Unauthorized" not in str(result)


def test_execute_request_sanitizes_403(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def _request_impl(**kwargs):  # type: ignore[no-untyped-def]
        return _FakeResponse(
            status_code=403,
            payload={"message": "Forbidden", "token": "supersecret"},
        )

    monkeypatch.setattr(
        "src.handlers.api_handler.httpx.Client",
        lambda **_kwargs: _FakeClient(_request_impl),
    )

    result = APIHandler(_settings()).execute_get_request(path="/vms", path_params={})

    assert "error" in result
    assert "supersecret" not in str(result)
    assert "Forbidden" not in str(result)
