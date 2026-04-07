"""Runtime API execution against Prism Central."""

from __future__ import annotations

from typing import Any

import httpx

from src.config import Settings


class APIHandler:
    """HTTP API executor for parsed operations."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def execute_get_request(
        self,
        path: str,
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute a GET request against Prism Central."""
        resolved_path = self._resolve_path(path, path_params or {})
        url = f"{self.settings.pc_base_url}{resolved_path}"
        auth = self._build_auth()
        with httpx.Client(
            verify=not self.settings.pc_insecure,
            timeout=self.settings.startup_timeout_seconds,
            auth=auth,
        ) as client:
            response = client.get(url, params=query_params or {}, headers=headers or {})
        return self._as_result(response)

    def execute_write_request(
        self,
        method: str,
        path: str,
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a write request (used only for explicitly allowed operations)."""
        resolved_path = self._resolve_path(path, path_params or {})
        url = f"{self.settings.pc_base_url}{resolved_path}"
        auth = self._build_auth()
        with httpx.Client(
            verify=not self.settings.pc_insecure,
            timeout=self.settings.startup_timeout_seconds,
            auth=auth,
        ) as client:
            response = client.request(
                method=method.upper(),
                url=url,
                params=query_params or {},
                headers=headers or {},
                json=body or {},
            )
        return self._as_result(response)

    @staticmethod
    def _resolve_path(path: str, path_params: dict[str, Any]) -> str:
        resolved_path = path
        for key, value in path_params.items():
            resolved_path = resolved_path.replace("{" + key + "}", str(value))
        return resolved_path

    def _build_auth(self) -> tuple[str, str] | None:
        username = self.settings.pc_username
        password = self.settings.pc_password.get_secret_value() if self.settings.pc_password else None
        if username and password:
            return (username, password)
        return None

    @staticmethod
    def _as_result(response: httpx.Response) -> dict[str, Any]:
        payload: Any
        try:
            payload = response.json()
        except ValueError:
            payload = response.text
        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "payload": payload,
        }
