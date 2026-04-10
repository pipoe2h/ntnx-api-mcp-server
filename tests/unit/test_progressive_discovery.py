"""Unit tests for progressive discovery helper behavior."""

from __future__ import annotations

import pytest

from src.generators import ToolGenerator
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
    assert names == ["listOperations", "getOperationSchema", "getCodeSample"]


def test_list_operations_filters_by_namespace_and_search() -> None:
    generator = ToolGenerator(_operations())
    namespace_filtered = generator.list_operations(namespace="vmm")
    assert len(namespace_filtered) == 1
    assert namespace_filtered[0]["operation"] == "getVmById"

    search_filtered = generator.list_operations(search="task")
    assert len(search_filtered) == 1
    assert search_filtered[0]["operation"] == "listTasks"


def test_get_operation_schema_and_code_sample() -> None:
    generator = ToolGenerator(_operations())
    schema = generator.get_operation_schema("getVmById")
    assert schema["namespace"] == "vmm"

    sample = generator.get_code_sample("getVmById", "python")
    assert sample is not None
    assert sample["lang"] == "python"

    assert generator.get_code_sample("getVmById", "go") is None


def test_get_operation_schema_raises_for_unknown_operation() -> None:
    generator = ToolGenerator(_operations())
    with pytest.raises(KeyError):
        generator.get_operation_schema("doesNotExist")
