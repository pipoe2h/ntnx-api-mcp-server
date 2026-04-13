"""Tool schema generation from parsed operations."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import asdict
from typing import Any

from src.parsers import OperationInfo


@dataclass(slots=True)
class ToolContractError(ValueError):
    """Validation error for namespace execute contract."""

    code: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "detail": self.detail}


class ToolGenerator:
    """Generate namespace-level tool schemas from parsed operations."""

    def __init__(self, operations: list[OperationInfo]) -> None:
        self.operations = operations

    def group_by_namespace(self) -> dict[str, list[OperationInfo]]:
        """Group parsed operations by namespace."""
        grouped: dict[str, list[OperationInfo]] = {}
        for operation in self.operations:
            grouped.setdefault(operation.namespace, []).append(operation)
        return grouped

    def build_namespace_tools(self) -> list[dict[str, Any]]:
        """Build compact `<namespace>_execute` tool schemas."""
        tools: list[dict[str, Any]] = []
        for namespace, operations in sorted(self.group_by_namespace().items()):
            operation_ids = [operation.operation_id for operation in operations]
            tools.append(
                {
                    "name": f"{namespace}_execute",
                    "description": (
                        f"Execute operations from the {namespace} namespace. "
                        "Use the operation field to select the exact API operation."
                    ),
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "operation": {"type": "string", "enum": operation_ids},
                            "_page": {"type": "integer", "minimum": 0},
                            "_limit": {"type": "integer", "minimum": 1, "maximum": 100},
                            "_filter": {"type": "string"},
                            "_orderby": {"type": "string"},
                            "_select": {"type": "string"},
                            "_expand": {"type": "string"},
                        },
                        "required": ["operation"],
                    },
                    "metadata": {
                        "namespace": namespace,
                        "operation_count": len(operation_ids),
                    },
                }
            )
        return tools

    def build_operation_index(self) -> dict[str, dict[str, Any]]:
        """Build lookup index keyed by operation id."""
        index: dict[str, dict[str, Any]] = {}
        for operation in self.operations:
            index[operation.operation_id] = asdict(operation)
        return index

    def validate_namespace_operation_request(
        self,
        namespace: str,
        operation: str,
        request_payload: dict[str, Any],
    ) -> None:
        """
        Validate request payload against namespace operation contract.

        Raises ToolContractError for invalid namespace/operation/parameters.
        """
        grouped = self.group_by_namespace()
        namespace_ops = grouped.get(namespace)
        if namespace_ops is None:
            raise ToolContractError(
                code="unknown_namespace",
                detail=f"Unknown namespace: {namespace}",
            )

        target = next((item for item in namespace_ops if item.operation_id == operation), None)
        if target is None:
            raise ToolContractError(
                code="unknown_operation",
                detail=f"Unknown operation '{operation}' for namespace '{namespace}'",
            )

        allowed_keys = {"operation", "_page", "_limit", "_filter", "_orderby", "_select", "_expand"}
        allowed_keys.update({parameter.name for parameter in target.parameters})

        invalid_keys = [key for key in request_payload if key not in allowed_keys]
        if invalid_keys:
            raise ToolContractError(
                code="invalid_parameters",
                detail=f"Unsupported request fields: {', '.join(sorted(invalid_keys))}",
            )
