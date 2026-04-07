"""Tool schema generation from parsed operations."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.parsers import OperationInfo


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
        """Build `<namespace>_execute` tool schemas."""
        tools: list[dict[str, Any]] = []
        for namespace, operations in sorted(self.group_by_namespace().items()):
            operation_ids = [operation.operation_id for operation in operations]
            tools.append(
                {
                    "name": f"{namespace}_execute",
                    "description": (
                        f"Execute operations from the {namespace} namespace. "
                        f"Available operations: {', '.join(operation_ids[:10])}"
                        + (", ..." if len(operation_ids) > 10 else "")
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
