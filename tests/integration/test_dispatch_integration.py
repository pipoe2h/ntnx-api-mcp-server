"""Integration-style tests for runtime dispatch flow."""

from __future__ import annotations

from src.config import Settings
from src.server import build_runtime_dispatcher


def test_dispatcher_lists_discovery_and_namespace_tools(tmp_path) -> None:  # type: ignore[no-untyped-def]
    artifacts_dir = tmp_path / "artifacts"
    default_dir = tmp_path / "defaults"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    default_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "vmm-v4.2-all-documentation.yaml").write_text(
        "\n".join(
            [
                "openapi: 3.0.0",
                "paths:",
                "  /vms:",
                "    get:",
                "      operationId: listVms",
                "      summary: List VMs",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(
        pc_host=None,
        artifacts_dir=artifacts_dir,
        default_artifacts_dir=default_dir,
    )
    dispatcher = build_runtime_dispatcher(settings)
    names = [tool["name"] for tool in dispatcher.list_tools()]
    assert "vmm_execute" in names
    assert "listOperations" in names
    assert "getOperationSchema" in names
    assert "getCodeSample" in names
    assert "getOperationPermissions" in names


def test_dispatcher_list_operations_roundtrip(tmp_path) -> None:  # type: ignore[no-untyped-def]
    artifacts_dir = tmp_path / "artifacts"
    default_dir = tmp_path / "defaults"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    default_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "prism-v4.2-all-documentation.yaml").write_text(
        "\n".join(
            [
                "openapi: 3.0.0",
                "paths:",
                "  /tasks:",
                "    get:",
                "      operationId: listTasks",
                "      summary: List tasks",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(
        pc_host=None,
        artifacts_dir=artifacts_dir,
        default_artifacts_dir=default_dir,
    )
    dispatcher = build_runtime_dispatcher(settings)
    result = dispatcher.call_tool("listOperations", {"namespace": "prism"})
    assert result.ok is True
    assert len(result.payload) == 1
    assert result.payload[0]["operation"] == "listTasks"
