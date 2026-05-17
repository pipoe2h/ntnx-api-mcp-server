"""Tool schema generation from parsed operations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.generators.models import OperationDiscoveryItem, ToolDefinition, ToolInputSchema
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
            tool = ToolDefinition(
                name=f"{namespace}_execute",
                description=(
                    f"Execute operations from the {namespace} namespace. "
                    "Use the operation field to select the exact API operation."
                ),
                inputSchema=ToolInputSchema(
                    properties={
                        "operation": {"type": "string", "enum": operation_ids},
                        "_page": {"type": "integer", "minimum": 0},
                        "_limit": {"type": "integer", "minimum": 1, "maximum": 100},
                        "_filter": {"type": "string"},
                        "_orderby": {"type": "string"},
                        "_select": {"type": "string"},
                        "_expand": {"type": "string"},
                    },
                    required=["operation"],
                ),
                metadata={"namespace": namespace, "operation_count": len(operation_ids)},
            )
            tools.append(tool.model_dump(by_alias=True, exclude_none=True))
        return tools

    def build_operation_index(self) -> dict[str, dict[str, Any]]:
        """Build lookup index keyed by operation id."""
        index: dict[str, dict[str, Any]] = {}
        for operation in self.operations:
            index[operation.operation_id] = asdict(operation)
        return index

    def build_discovery_tools(self) -> list[dict[str, Any]]:
        """Build progressive disclosure helper tool schemas."""
        definitions = [
            ToolDefinition(
                name="listOperations",
                description="List available operations, optionally filtered by namespace or search text.",
                inputSchema=ToolInputSchema(
                    properties={
                        "namespace": {"type": "string"},
                        "search": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 500},
                        "offset": {"type": "integer", "minimum": 0},
                    }
                ),
            ),
            ToolDefinition(
                name="getOperationSchema",
                description="Get full schema details for a specific operation id.",
                inputSchema=ToolInputSchema(
                    properties={"operation": {"type": "string"}},
                    required=["operation"],
                ),
            ),
            ToolDefinition(
                name="getCodeSample",
                description="Get a language-specific code sample for an operation when available.",
                inputSchema=ToolInputSchema(
                    properties={
                        "operation": {"type": "string"},
                        "language": {"type": "string"},
                    },
                    required=["operation", "language"],
                ),
            ),
            ToolDefinition(
                name="getOperationPermissions",
                description="Get required roles/permissions metadata for a specific operation id.",
                inputSchema=ToolInputSchema(
                    properties={"operation": {"type": "string"}},
                    required=["operation"],
                ),
            ),
        ]
        return [definition.model_dump(by_alias=True, exclude_none=True) for definition in definitions]

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

        items: list[OperationDiscoveryItem] = []
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
                OperationDiscoveryItem(
                    namespace=operation.namespace,
                    operation=operation.operation_id,
                    method=operation.method,
                    path=operation.path,
                    summary=operation.summary,
                    permission_name=self._extract_permission_name(operation.permissions),
                    required_roles=operation.required_roles,
                )
            )

        items.sort(key=lambda value: (value.namespace, value.operation))
        return [item.model_dump() for item in items[offset : offset + limit]]

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

    def get_operation_permissions(self, operation_id: str) -> dict[str, Any]:
        """Return permission metadata and required roles for an operation id."""
        schema = self.get_operation_schema(operation_id)
        permissions = schema.get("permissions")
        permission_name = (
            permissions.get("operationName")
            if isinstance(permissions, dict) and isinstance(permissions.get("operationName"), str)
            else None
        )
        return {
            "operation": schema["operation_id"],
            "namespace": schema["namespace"],
            "method": schema["method"],
            "path": schema["path"],
            "permission_name": permission_name,
            "required_roles": schema.get("required_roles", []),
            "raw_permissions": permissions,
        }

    @staticmethod
    def _extract_permission_name(permissions: dict[str, Any] | None) -> str | None:
        if permissions is None:
            return None
        operation_name = permissions.get("operationName")
        if isinstance(operation_name, str) and operation_name.strip():
            return operation_name.strip()
        return None

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
