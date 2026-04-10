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

    def build_discovery_tools(self) -> list[dict[str, Any]]:
        """Build progressive disclosure helper tool schemas."""
        return [
            {
                "name": "listOperations",
                "description": "List available operations, optionally filtered by namespace or search text.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "namespace": {"type": "string"},
                        "search": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 500},
                        "offset": {"type": "integer", "minimum": 0},
                    },
                },
            },
            {
                "name": "getOperationSchema",
                "description": "Get full schema details for a specific operation id.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"operation": {"type": "string"}},
                    "required": ["operation"],
                },
            },
            {
                "name": "getCodeSample",
                "description": "Get a language-specific code sample for an operation when available.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "operation": {"type": "string"},
                        "language": {"type": "string"},
                    },
                    "required": ["operation", "language"],
                },
            },
        ]

    def list_operations(
        self,
        namespace: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List operations with optional namespace/search filtering and pagination."""
        normalized_namespace = namespace.strip() if isinstance(namespace, str) else None
        normalized_search = search.lower().strip() if isinstance(search, str) else None

        items: list[dict[str, Any]] = []
        for operation in self.operations:
            if normalized_namespace and operation.namespace != normalized_namespace:
                continue
            if normalized_search:
                content = " ".join(
                    [
                        operation.operation_id,
                        operation.path,
                        operation.summary,
                        operation.description,
                    ]
                ).lower()
                if normalized_search not in content:
                    continue
            items.append(
                {
                    "namespace": operation.namespace,
                    "operation": operation.operation_id,
                    "method": operation.method,
                    "path": operation.path,
                    "summary": operation.summary,
                }
            )

        items.sort(key=lambda value: (value["namespace"], value["operation"]))
        return items[offset : offset + limit]

    def get_operation_schema(self, operation_id: str) -> dict[str, Any]:
        """Return detailed schema dictionary for an operation id."""
        operation_index = self.build_operation_index()
        if operation_id not in operation_index:
            raise KeyError(f"Unknown operation id: {operation_id}")
        return operation_index[operation_id]

    def get_code_sample(self, operation_id: str, language: str) -> dict[str, Any] | None:
        """Return the best matching code sample for operation/language."""
        schema = self.get_operation_schema(operation_id)
        requested = language.lower().strip()
        for sample in schema.get("code_samples", []):
            sample_language = sample.get("lang") or sample.get("language")
            if isinstance(sample_language, str) and sample_language.lower() == requested:
                return sample
        return None
