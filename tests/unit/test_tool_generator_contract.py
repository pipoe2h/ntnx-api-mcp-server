"""Unit tests for namespace tool contract behavior."""

from __future__ import annotations

import pytest

from src.generators import ToolContractError, ToolGenerator
from src.parsers import OperationInfo, ParameterInfo


def _operation() -> OperationInfo:
    return OperationInfo(
        namespace="vmm",
        operation_id="getVmById",
        path="/vms/{vmId}",
        method="GET",
        summary="Get VM",
        description="Get VM by id",
        parameters=[
            ParameterInfo(name="vmId", location="path", required=True),
            ParameterInfo(name="$filter", location="query", required=False),
        ],
    )


def test_namespace_tool_description_is_compact() -> None:
    tools = ToolGenerator([_operation()]).build_namespace_tools()
    assert len(tools) == 1
    description = tools[0]["description"]
    assert "Use the operation field" in description
    assert "Available operations:" not in description


def test_validate_operation_request_accepts_allowed_fields() -> None:
    generator = ToolGenerator([_operation()])
    generator.validate_namespace_operation_request(
        namespace="vmm",
        operation="getVmById",
        request_payload={
            "operation": "getVmById",
            "vmId": "1234",
            "_filter": "name eq 'a'",
            "request_body": {"foo": "bar"},
        },
    )


def test_validate_operation_request_rejects_unknown_fields() -> None:
    generator = ToolGenerator([_operation()])
    with pytest.raises(ToolContractError) as exc:
        generator.validate_namespace_operation_request(
            namespace="vmm",
            operation="getVmById",
            request_payload={"operation": "getVmById", "unknownField": "x"},
        )
    assert exc.value.code == "invalid_parameters"


def test_validate_operation_request_rejects_non_object_body() -> None:
    generator = ToolGenerator([_operation()])
    with pytest.raises(ToolContractError) as exc:
        generator.validate_namespace_operation_request(
            namespace="vmm",
            operation="getVmById",
            request_payload={"operation": "getVmById", "request_body": "bad"},
        )
    assert exc.value.code == "invalid_parameters"
