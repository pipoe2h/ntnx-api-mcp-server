"""Unit tests for progressive discovery helper behavior."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.generators import ToolGenerator
from src.generators.models import ToolDefinition, ToolInputSchema
from src.parsers import OperationInfo, ParameterInfo


def _operations() -> list[OperationInfo]:
    return [
        OperationInfo(
            namespace="vmm",
            operation_id="getVmById",
            path="/vms/{vmId}",
            method="GET",
            summary="Get VM by id",
            description="Get VM details by identifier",
            parameters=[ParameterInfo(name="vmId", location="path", required=True)],
            code_samples=[{"lang": "python", "source": "print('vm')"}],
            permissions={
                "operationName": "View VM",
                "roleList": [{"name": "Prism Viewer"}, {"name": "Prism Admin"}],
            },
            required_roles=["Prism Viewer", "Prism Admin"],
        ),
        OperationInfo(
            namespace="prism",
            operation_id="listTasks",
            path="/tasks",
            method="GET",
            summary="List tasks",
            description="List task entities",
        ),
    ]


def test_build_discovery_tools_has_expected_helpers() -> None:
    tools = ToolGenerator(_operations()).build_discovery_tools()
    names = [tool["name"] for tool in tools]
    assert names == ["listOperations", "getOperationSchema", "getCodeSample", "getOperationPermissions"]


def test_list_operations_filters_by_namespace_and_search() -> None:
    generator = ToolGenerator(_operations())
    namespace_filtered = generator.list_operations(namespace="vmm")
    assert len(namespace_filtered) == 1
    assert namespace_filtered[0]["operation"] == "getVmById"
    assert namespace_filtered[0]["permission_name"] == "View VM"
    assert "Prism Viewer" in namespace_filtered[0]["required_roles"]

    search_filtered = generator.list_operations(search="task")
    assert len(search_filtered) == 1
    assert search_filtered[0]["operation"] == "listTasks"


def test_get_operation_schema_and_code_sample() -> None:
    generator = ToolGenerator(_operations())
    schema = generator.get_operation_schema("getVmById")
    # New structured shape: keyed by operation, method, path, parameters, body fields.
    assert schema["operation"] == "getVmById"
    assert schema["method"] == "GET"
    assert schema["path"] == "/vms/{vmId}"
    assert any(p["name"] == "vmId" for p in schema["path_parameters"])
    assert "request_body_schema" in schema
    assert "immutable_fields" in schema

    sample = generator.get_code_sample("getVmById", "python")
    assert sample is not None
    assert sample["lang"] == "python"

    assert generator.get_code_sample("getVmById", "go") is None

    permissions = generator.get_operation_permissions("getVmById")
    assert permissions["permission_name"] == "View VM"
    assert "Prism Admin" in permissions["required_roles"]


def test_get_operation_schema_raises_for_unknown_operation() -> None:
    generator = ToolGenerator(_operations())
    with pytest.raises(KeyError):
        generator.get_operation_schema("doesNotExist")


def test_tool_models_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ToolInputSchema(properties={"operation": {"type": "string"}}, unknown="x")

    with pytest.raises(ValidationError):
        ToolDefinition(
            name="listOperations",
            description="desc",
            inputSchema=ToolInputSchema(properties={}),
            unknown="x",
        )
