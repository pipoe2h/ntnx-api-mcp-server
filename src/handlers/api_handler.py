"""Runtime API execution against Prism Central."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote
from uuid import uuid4

import httpx

from src.auth import build_auth_context
from src.config import Settings


class APIHandler:
    """HTTP API executor for parsed operations."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def execute_request(
        self,
        method: str,
        path: str,
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request against Prism Central."""
        resolved_path = self._resolve_path(path, path_params or {})

        normalized_query = self._normalize_query_params(query_params or {})
        normalized_headers = self._normalize_headers(headers or {})
        auth, auth_headers = build_auth_context(self.settings)
        normalized_headers.update(auth_headers)
        # Idempotency header required by Nutanix V4 APIs — auto-generated per call.
        if "NTNX-Request-Id" not in normalized_headers:
            normalized_headers["NTNX-Request-Id"] = str(uuid4())
        # Auto-fetch ETag for mutating operations that require optimistic locking.
        upper_method = method.upper()
        if upper_method in {"PUT", "PATCH", "DELETE"} and "If-Match" not in normalized_headers:
            etag = self._fetch_etag(resolved_path, auth, auth_headers)
            if etag:
                normalized_headers["If-Match"] = etag
        url = f"{self.settings.pc_base_url}{resolved_path}"
        with httpx.Client(
            verify=not self.settings.pc_insecure,
            timeout=self.settings.startup_timeout_seconds,
            auth=auth,
        ) as client:
            response = client.request(
                upper_method,
                url,
                params=normalized_query,
                headers=normalized_headers,
                json=body if body is not None else None,
            )
        return self._as_result(response)

    def _fetch_etag(
        self, resolved_path: str, auth: Any, auth_headers: dict[str, str]
    ) -> str | None:
        """GET the resource and return its ETag for optimistic locking.

        Action endpoints (/$actions/) do not use ETags — skipped.
        Checks both the response header and $reserved.etag in the body
        (some Nutanix APIs embed it in the body rather than returning a header).
        Returns None on any failure so the caller proceeds without If-Match.
        """
        if "/$actions/" in resolved_path:
            return None
        url = f"{self.settings.pc_base_url}{resolved_path}"
        get_headers = dict(auth_headers)
        get_headers["NTNX-Request-Id"] = str(uuid4())
        try:
            with httpx.Client(
                verify=not self.settings.pc_insecure,
                timeout=self.settings.startup_timeout_seconds,
                auth=auth,
            ) as client:
                response = client.get(url, headers=get_headers)
            etag = response.headers.get("ETag")
            if not etag and response.status_code == 200:
                # Fallback: some Nutanix APIs embed ETag in $reserved.etag in the body.
                try:
                    body = response.json()
                    if isinstance(body, dict):
                        inner = body.get("data", body)
                        if isinstance(inner, dict):
                            reserved = inner.get("$reserved", {})
                            if isinstance(reserved, dict):
                                etag = reserved.get("etag")
                except ValueError:
                    pass
            return etag
        except (httpx.HTTPError, httpx.NetworkError, ValueError):
            return None

    @staticmethod
    def _resolve_path(path: str, path_params: dict[str, Any]) -> str:
        placeholders = APIHandler._extract_path_placeholders(path)
        missing_keys = sorted(name for name in placeholders if name not in path_params)
        if missing_keys:
            raise ValueError(f"Missing required path parameters: {', '.join(missing_keys)}")

        extra_keys = sorted(name for name in path_params if name not in placeholders)
        if extra_keys:
            raise ValueError(f"Unexpected path parameters: {', '.join(extra_keys)}")

        resolved_path = path
        for key in placeholders:
            raw_value = path_params[key]
            if raw_value is None:
                raise ValueError(f"Path parameter '{key}' cannot be null.")
            encoded_value = quote(str(raw_value), safe="")
            resolved_path = resolved_path.replace("{" + key + "}", encoded_value)
        return resolved_path

    @staticmethod
    def _extract_path_placeholders(path: str) -> list[str]:
        placeholders: list[str] = []
        start = 0
        while True:
            left = path.find("{", start)
            if left == -1:
                break
            right = path.find("}", left + 1)
            if right == -1:
                break
            name = path[left + 1 : right].strip()
            if name:
                placeholders.append(name)
            start = right + 1
        return placeholders

    @staticmethod
    def _normalize_query_params(query_params: dict[str, Any]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, value in query_params.items():
            if value is None:
                continue
            if isinstance(value, bool):
                normalized[key] = "true" if value else "false"
            elif isinstance(value, (list, tuple, set)):
                values = [str(item) for item in value if item is not None]
                if values:
                    normalized[key] = ",".join(values)
            else:
                normalized[key] = str(value)
        return normalized

    @staticmethod
    def _normalize_headers(headers: dict[str, Any]) -> dict[str, str]:
        return {str(key): str(value) for key, value in headers.items() if value is not None}

    @staticmethod
    def _as_result(response: httpx.Response) -> dict[str, Any]:
        payload: Any
        try:
            payload = response.json()
        except ValueError:
            payload = {"data": response.text}
        return payload if isinstance(payload, dict) else {"data": payload}
