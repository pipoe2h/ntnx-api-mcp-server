"""Runtime API execution against Prism Central."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

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
        url = f"{self.settings.pc_base_url}{resolved_path}"
        with httpx.Client(
            verify=not self.settings.pc_insecure,
            timeout=self.settings.startup_timeout_seconds,
            auth=auth,
        ) as client:
            response = client.request(
                method.upper(),
                url,
                params=normalized_query,
                headers=normalized_headers,
                json=body if body is not None else None,
            )
        return self._as_result(response)

    def execute_get_request(
        self,
        path: str,
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Backward-compatible GET helper."""
        return self.execute_request(
            method="GET",
            path=path,
            path_params=path_params,
            query_params=query_params,
            headers=headers,
            body=None,
        )

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
