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
        permissions={
            "operationName": "View VM",
            "roleList": [{"name": "Prism Viewer"}, {"name": "Prism Admin"}],
        },
        required_roles=["Prism Viewer", "Prism Admin"],
    )
    from src.generators import ToolGenerator
    load_result = StartupLoadResult(
        artifacts_source="runtime",
        artifact_directory=Settings().artifacts_dir,
        files=[],
        operations=[operation],
        namespace_tools=[],
        discovery_tools=[],
        operation_index={},
        generator=ToolGenerator([operation], schemas={}, namespace_metadata={}),
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
    # New structured shape: 'operation' holds the registered name.
    assert result.payload["operation"] == "getVmById"
    assert result.payload["method"] == "GET"
    assert result.payload["path"] == "/vms/{vmId}"


def test_get_code_sample_helper() -> None:
    dispatcher = _build_dispatcher()
    result = dispatcher.call_tool("getCodeSample", {"operation": "getVmById", "language": "python"})
    assert result.ok is True
    assert result.payload["lang"] == "python"


def test_get_operation_permissions_helper() -> None:
    dispatcher = _build_dispatcher()
    result = dispatcher.call_tool("getOperationPermissions", {"operation": "getVmById"})
    assert result.ok is True
    assert result.payload["permission_name"] == "View VM"
    assert "Prism Viewer" in result.payload["required_roles"]


def test_namespace_execute_with_odata_alias(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    dispatcher = _build_dispatcher()

    captured = {}

    def _fake_execute_request(
        method, path, path_params=None, query_params=None, headers=None, body=None
    ):  # type: ignore[no-untyped-def]
        captured["method"] = method
        captured["path"] = path
        captured["path_params"] = path_params
        captured["query_params"] = query_params
        captured["headers"] = headers
        captured["body"] = body
        return {"metadata": {"messages": []}, "data": [{"extId": "x"}]}

    monkeypatch.setattr(dispatcher.api_handler, "execute_request", _fake_execute_request)

    result = dispatcher.call_tool(
        "vmm_execute",
        {
            "operation": "getVmById",
            "vmId": "vm-123",
            "_limit": 10,
        },
    )

    assert result.ok is True
    assert captured["method"] == "GET"
    assert captured["path"] == "/vms/{vmId}"
    assert captured["path_params"]["vmId"] == "vm-123"
    assert captured["query_params"]["$limit"] == 10
    assert captured["body"] is None


def test_namespace_execute_for_post_with_request_body(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    operation = OperationInfo(
        namespace="vmm",
        operation_id="createVm",
        path="/vms",
        method="POST",
        summary="Create VM",
        description="Create VM",
        request_body={"content": {"application/json": {"schema": {"type": "object"}}}},
    )
    from src.generators import ToolGenerator
    load_result = StartupLoadResult(
        artifacts_source="runtime",
        artifact_directory=Settings().artifacts_dir,
        files=[],
        operations=[operation],
        namespace_tools=[],
        discovery_tools=[],
        operation_index={},
        generator=ToolGenerator([operation], schemas={}, namespace_metadata={}),
    )
    dispatcher = RuntimeToolDispatcher(
        settings=Settings(pc_host="127.0.0.1", pc_port=9440),
        load_result=load_result,
    )

    captured = {}

    def _fake_execute_request(
        method, path, path_params=None, query_params=None, headers=None, body=None
    ):  # type: ignore[no-untyped-def]
        captured["method"] = method
        captured["path"] = path
        captured["body"] = body
        return {"data": {"ok": True}}

    monkeypatch.setattr(dispatcher.api_handler, "execute_request", _fake_execute_request)

    result = dispatcher.call_tool(
        "vmm_execute",
        {
            "operation": "createVm",
            "request_body": {"name": "vm-1"},
        },
    )

    assert result.ok is True
    assert captured["method"] == "POST"
    assert captured["path"] == "/vms"
    assert captured["body"] == {"name": "vm-1"}


def test_readonly_mode_blocks_non_get(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """read_only_mode=True must reject POST/PUT/PATCH/DELETE before reaching the API."""
    operation = OperationInfo(
        namespace="vmm",
        operation_id="createVm",
        path="/vms",
        method="POST",
        summary="Create VM",
        description="Create VM",
        request_body={"content": {"application/json": {"schema": {"type": "object"}}}},
    )
    from src.generators import ToolGenerator
    load_result = StartupLoadResult(
        artifacts_source="runtime",
        artifact_directory=Settings().artifacts_dir,
        files=[],
        operations=[operation],
        namespace_tools=[],
        discovery_tools=[],
        operation_index={},
        generator=ToolGenerator([operation], schemas={}, namespace_metadata={}),
    )
    dispatcher = RuntimeToolDispatcher(
        settings=Settings(pc_host="127.0.0.1", pc_port=9440, read_only_mode=True),
        load_result=load_result,
    )

    called = {"count": 0}

    def _should_not_be_called(**kwargs):  # type: ignore[no-untyped-def]
        called["count"] += 1
        return {}

    monkeypatch.setattr(dispatcher.api_handler, "execute_request", _should_not_be_called)

    result = dispatcher.call_tool(
        "vmm_execute",
        {"operation": "createVm", "request_body": {"name": "vm-1"}},
    )

    assert result.ok is False
    assert result.error is not None
    assert result.error["code"] == "read_only_mode"
    assert called["count"] == 0
