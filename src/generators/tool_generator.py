"""Tool schema generation from parsed operations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

from src.generators.models import OperationDiscoveryItem, ToolDefinition, ToolInputSchema
from src.generators.payload_validator import validate_payload
from src.generators.schema_resolver import resolve_request_body_schema
from src.parsers import OperationInfo
from src.parsers.yaml_parser import _camel_to_tokens

_VERSION_RE = re.compile(r"^v\d+", re.IGNORECASE)


def _score_operation(
    operation: OperationInfo,
    query_tokens: list[str],
) -> tuple[int, list[str]]:
    """Score an operation against query tokens using field-weighted matching.

    Returns (score, matched_fields). Score 0 means no match (all tokens must hit).
    Higher score = stronger relevance. Fields checked in order of signal strength:
      registered_name (raw)      -> 50 pts per token  (callable name, variant-aware)
      operation_id (raw)         -> 50 pts per token  (spec name; same tier as registered_name)
      operation_id (camel split) -> 40 pts per token
      summary                    -> 20 pts per token
      path tokens                -> 10 pts per token
      enriched search_text       ->  5 pts per token (tag names, descriptions)
    Bonus: +20 when ALL tokens matched in a single high-signal field (concentrated match).
    """
    op_id_lower = operation.operation_id.lower()
    # registered_name differs from operation_id only for variant operations (e.g. ahv_listVms).
    # Score it at the same tier so variant discriminators ("ahv", "esxi") rank correctly.
    reg_name_lower = operation.registered_name.lower()
    reg_name_differs = reg_name_lower != op_id_lower
    op_id_tokens = set(_camel_to_tokens(operation.operation_id).split())
    summary_lower = operation.summary.lower()
    # Path tokens: split on / and strip version segments and braces
    version_re = _VERSION_RE
    path_tokens_text = " ".join(
        seg.replace("-", " ").replace("_", " ").lower()
        for seg in operation.path.split("/")
        if seg and not seg.startswith("{") and not version_re.match(seg)
    )
    search_text = operation.search_text

    score = 0
    matched_fields: list[str] = []
    field_hits: dict[str, int] = {}

    for token in query_tokens:
        hit = False
        if token in op_id_lower or (reg_name_differs and token in reg_name_lower):
            score += 50
            field_hits["operation_id"] = field_hits.get("operation_id", 0) + 1
            hit = True
        elif token in op_id_tokens:
            score += 40
            field_hits["operation_id"] = field_hits.get("operation_id", 0) + 1
            hit = True
        if token in summary_lower:
            score += 20
            field_hits["summary"] = field_hits.get("summary", 0) + 1
            hit = True
        if token in path_tokens_text:
            score += 10
            field_hits["path"] = field_hits.get("path", 0) + 1
            hit = True
        if token in search_text and not hit:
            # Catch tag names, descriptions, CamelCase expansions not yet scored above.
            score += 5
            field_hits["search_text"] = field_hits.get("search_text", 0) + 1
            hit = True

        if not hit:
            # Token not found anywhere — AND semantics: entire operation is not a match.
            return 0, []

    # Concentrated match bonus: all tokens hit the same high-signal field.
    if field_hits.get("operation_id", 0) == len(query_tokens):
        score += 20
    elif field_hits.get("summary", 0) == len(query_tokens):
        score += 10

    matched_fields = sorted(field_hits.keys())
    return score, matched_fields


@dataclass(slots=True)
class ToolContractError(ValueError):
    """Validation error for namespace execute contract."""

    code: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "detail": self.detail}


class ToolGenerator:
    """Generate namespace-level tool schemas from parsed operations."""

    def __init__(
        self,
        operations: list[OperationInfo],
        component_schemas: dict[str, Any] | None = None,
    ) -> None:
        self.operations = operations
        self.component_schemas: dict[str, Any] = component_schemas or {}

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
            # registered_name is guaranteed unique within a namespace by resolve_collisions().
            registered_names = [op.registered_name for op in operations]
            tool = ToolDefinition(
                name=f"{namespace}_execute",
                description=(
                    f"Execute operations from the {namespace} namespace. "
                    "Use the operation field to select the exact API operation. "
                    "For POST/PUT/PATCH operations, pass the request body as 'request_body'. "
                    "Pass operation-specific path and query parameters (e.g. extId, vmExtId) "
                    "as direct top-level keyword arguments alongside 'operation'."
                ),
                inputSchema=ToolInputSchema(
                    properties={
                        "operation": {"type": "string", "enum": registered_names},
                        "_page": {"type": "integer", "minimum": 0},
                        "_limit": {"type": "integer", "minimum": 1, "maximum": 100},
                        "_filter": {"type": "string"},
                        "_orderby": {"type": "string"},
                        "_select": {"type": "string"},
                        "_expand": {"type": "string"},
                        "request_body": {"type": "object"},
                    },
                    required=["operation"],
                ),
                metadata={"namespace": namespace, "operation_count": len(registered_names)},
            )
            tools.append(tool.model_dump(by_alias=True, exclude_none=True))
        return tools

    def build_operation_index(self) -> dict[str, dict[str, Any]]:
        """Build lookup index keyed by registered_name (guaranteed unique per namespace)."""
        index: dict[str, dict[str, Any]] = {}
        for operation in self.operations:
            index[operation.registered_name] = asdict(operation)
        return index

    def build_discovery_tools(self) -> list[dict[str, Any]]:
        """Build progressive disclosure helper tool schemas."""
        definitions = [
            ToolDefinition(
                name="listOperations",
                description=(
                    "List available API operations, optionally filtered by namespace or search terms. "
                    "Results are ranked by relevance score (descending) when a search term is provided — "
                    "position 1 is the server's highest-confidence match. "
                    "Each result includes relevance_score (higher = stronger match) and match_fields "
                    "(the fields where your tokens were found). "
                    "match_fields containing 'operation_id' is a strong signal; 'search_text' only is weak. "
                    "Use 1-2 keyword tokens for best results. Default limit is 20."
                ),
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
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List operations with optional namespace/search filtering, ranked by relevance."""
        normalized_namespace = namespace.strip() if isinstance(namespace, str) else None
        query_tokens = (
            [t for t in search.lower().split() if t]
            if isinstance(search, str) and search.strip()
            else []
        )

        scored: list[tuple[int, list[str], OperationDiscoveryItem]] = []

        for operation in self.operations:
            if normalized_namespace and operation.namespace != normalized_namespace:
                continue

            if query_tokens:
                score, matched_fields = _score_operation(operation, query_tokens)
                if score == 0:
                    continue
            else:
                score, matched_fields = 0, []

            scored.append((
                score,
                matched_fields,
                OperationDiscoveryItem(
                    namespace=operation.namespace,
                    operation=operation.registered_name,
                    method=operation.method,
                    path=operation.path,
                    summary=operation.summary,
                    permission_name=self._extract_permission_name(operation.permissions),
                    required_roles=operation.required_roles,
                    relevance_score=score if query_tokens else None,
                    match_fields=matched_fields,
                    spec_operation_id=(
                        operation.operation_id
                        if operation.path_variant is not None
                        else None
                    ),
                    path_variant=operation.path_variant,
                ),
            ))

        if query_tokens:
            # Sort by score descending, then alphabetically for stable tie-breaking.
            scored.sort(key=lambda x: (-x[0], x[2].namespace, x[2].operation))
        else:
            scored.sort(key=lambda x: (x[2].namespace, x[2].operation))

        page = scored[offset: offset + limit]
        return [item.model_dump() for _, _, item in page]

    def get_operation_schema(self, operation_id: str) -> dict[str, Any]:
        """Return detailed schema dictionary for an operation id.

        Includes a resolved request_body_schema field when the operation has a
        request body with $ref types — resolved from the in-memory component schemas.
        """
        operation = next(
            (op for op in self.operations if op.registered_name == operation_id),
            None,
        )
        if operation is None:
            raise KeyError(f"Unknown operation id: {operation_id}")
        schema = asdict(operation)
        raw_rb = schema.get("request_body")
        if raw_rb and self.component_schemas:
            schema["request_body_schema"] = resolve_request_body_schema(
                raw_rb, self.component_schemas
            )
        else:
            schema["request_body_schema"] = None
        # Surface path/query parameters as a structured summary so the LLM knows
        # which top-level keyword arguments to pass in the execute tool call.
        raw_params = schema.get("parameters", [])
        schema["parameter_summary"] = [
            {
                "name": p.get("name"),
                "location": p.get("location"),
                "required": p.get("required", False),
                "type": p.get("schema", {}).get("type", "string"),
                "description": p.get("description"),
            }
            for p in raw_params
            if isinstance(p, dict) and p.get("location") in ("path", "query")
        ]
        # List immutable fields (readOnly in spec) so the LLM knows which fields
        # must be echoed back unchanged from GET but must NOT be modified.
        # For Nutanix full-PUT operations: include these from GET, do not change them.
        rb_schema = schema.get("request_body_schema")
        schema["immutable_fields"] = [
            fname
            for fname, fprop in (rb_schema or {}).get("properties", {}).items()
            if isinstance(fprop, dict) and fprop.get("readOnly")
        ]
        return schema

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

        target = next((item for item in namespace_ops if item.registered_name == operation), None)
        if target is None:
            raise ToolContractError(
                code="unknown_operation",
                detail=f"Unknown operation '{operation}' for namespace '{namespace}'",
            )

        allowed_keys = {
            "operation",
            "_page",
            "_limit",
            "_filter",
            "_orderby",
            "_select",
            "_expand",
            "request_body",
        }
        allowed_keys.update({parameter.name for parameter in target.parameters})

        invalid_keys = [key for key in request_payload if key not in allowed_keys]
        if invalid_keys:
            raise ToolContractError(
                code="invalid_parameters",
                detail=f"Unsupported request fields: {', '.join(sorted(invalid_keys))}",
            )
        if "request_body" in request_payload and request_payload["request_body"] is not None:
            if not isinstance(request_payload["request_body"], dict):
                raise ToolContractError(
                    code="invalid_parameters",
                    detail="request_body must be an object when provided.",
                )

