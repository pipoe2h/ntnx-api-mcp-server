"""Tests for the Streamable HTTP application."""

from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

from src.config import Settings
from src.mcp_http_server import create_http_app


def test_health_endpoint(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "vmm-v4.2-all-documentation.yaml").write_text(
        "openapi: 3.0.0\npaths: {}\n",
        encoding="utf-8",
    )
    settings = Settings(
        pc_host=None,
        artifacts_dir=artifacts,
        default_artifacts_dir=tmp_path / "defaults",
        log_dir=tmp_path / "logs",
    )

    with TestClient(create_http_app(settings)) as client:
        response = client.get("/health")
        mcp_response = client.post(
            "/mcp",
            headers={"accept": "application/json, text/event-stream"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1"},
                },
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert mcp_response.status_code == 200
