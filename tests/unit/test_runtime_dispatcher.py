"""Unit tests for runtime dispatch wiring."""

from __future__ import annotations

from src.config import Settings
from src.parsers import OperationInfo, ParameterInfo
from src.server import StartupLoadResult
from src.tools import RuntimeToolDispatcher


def _build_dispatcher() -> RuntimeToolDispatcher:
    operation = OperationInfo(
        namespace="vmm",
        operation_id="getVmById",
        path="/vms/{vmId}",
        method="GET",
        summary="Get VM",
        description="Get VM by ID",
        parameters=[
            ParameterInfo(name="vmId", location="path", required=True),
            ParameterInfo(name="$limit", location="query", required=False),
        ],
        code_samples=[{"lang": "python", "source": "print('hello')"}],
    )
    load_result = StartupLoadResult(
        artifacts_source="runtime",
        artifact_directory=Settings().artifacts_dir,
        files=[],
        operations=[operation],
        namespace_tools=[],
        discovery_tools=[],
        operation_index={},
    )
    settings = Settings(pc_host="127.0.0.1", pc_port=9440)
    return RuntimeToolDispatcher(settings=settings, load_result=load_result)


def test_list_operations_helper() -> None:
    dispatcher = _build_dispatcher()
    result = dispatcher.call_tool("listOperations", {"namespace": "vmm"})
    assert result.ok is True
    assert len(result.payload) == 1
    assert result.payload[0]["operation"] == "getVmById"


def test_get_operation_schema_helper() -> None:
    dispatcher = _build_dispatcher()
    result = dispatcher.call_tool("getOperationSchema", {"operation": "getVmById"})
    assert result.ok is True
    assert result.payload["operation_id"] == "getVmById"


def test_get_code_sample_helper() -> None:
    dispatcher = _build_dispatcher()
    result = dispatcher.call_tool("getCodeSample", {"operation": "getVmById", "language": "python"})
    assert result.ok is True
    assert result.payload["lang"] == "python"


def test_namespace_execute_with_odata_alias(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    dispatcher = _build_dispatcher()

    captured = {}

    def _fake_execute_get_request(path, path_params=None, query_params=None, headers=None):  # type: ignore[no-untyped-def]
        captured["path"] = path
        captured["path_params"] = path_params
        captured["query_params"] = query_params
        captured["headers"] = headers
        return {"metadata": {"messages": []}, "data": [{"extId": "x"}]}

    monkeypatch.setattr(dispatcher.api_handler, "execute_get_request", _fake_execute_get_request)

    result = dispatcher.call_tool(
        "vmm_execute",
        {
            "operation": "getVmById",
            "vmId": "vm-123",
            "_limit": 10,
        },
    )

    assert result.ok is True
    assert captured["path"] == "/vms/{vmId}"
    assert captured["path_params"]["vmId"] == "vm-123"
    assert captured["query_params"]["$limit"] == 10
