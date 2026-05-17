"""OpenAPI YAML parser for operation extraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class ParameterInfo:
    """Operation parameter metadata."""

    name: str
    location: str
    required: bool
    schema: dict[str, Any] = field(default_factory=dict)
    description: str | None = None


@dataclass(slots=True)
class OperationInfo:
    """Parsed operation metadata used by tool generation."""

    namespace: str
    operation_id: str
    path: str
    method: str
    summary: str
    description: str
    tags: list[str] = field(default_factory=list)
    parameters: list[ParameterInfo] = field(default_factory=list)
    code_samples: list[dict[str, Any]] = field(default_factory=list)
    request_body: dict[str, Any] | None = None
    permissions: dict[str, Any] | None = None
    required_roles: list[str] = field(default_factory=list)


class OpenAPIParser:
    """Parser for v4 OpenAPI YAML specifications."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.spec: dict[str, Any] = {}

    def load(self) -> dict[str, Any]:
        """Load and return OpenAPI document."""
        with self.file_path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
        if not isinstance(loaded, dict):
            raise ValueError(f"YAML root must be an object in {self.file_path}")
        self.spec = loaded
        return self.spec

    def extract_get_operations(self, namespace: str) -> list[OperationInfo]:
        """Extract GET operations from OpenAPI paths."""
        if not self.spec:
            self.load()
        paths = self.spec.get("paths", {})
        if not isinstance(paths, dict):
            return []

        operations: list[OperationInfo] = []
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            get_item = path_item.get("get")
            if not isinstance(get_item, dict):
                continue
            operation = self._build_operation(namespace, path, "get", get_item, path_item)
            if operation is not None:
                operations.append(operation)
        return operations

    def _build_operation(
        self,
        namespace: str,
        path: str,
        method: str,
        op_item: dict[str, Any],
        path_item: dict[str, Any],
    ) -> OperationInfo | None:
        operation_id = op_item.get("operationId")
        if not isinstance(operation_id, str) or not operation_id.strip():
            return None

        parameters = self._extract_parameters(op_item, path_item)
        summary = op_item.get("summary") if isinstance(op_item.get("summary"), str) else ""
        description_value = op_item.get("description")
        description = description_value if isinstance(description_value, str) else summary

        tags_value = op_item.get("tags")
        tags = tags_value if isinstance(tags_value, list) else []

        code_samples_value = op_item.get("x-codeSamples")
        code_samples = code_samples_value if isinstance(code_samples_value, list) else []

        request_body = op_item.get("requestBody")
        if not isinstance(request_body, dict):
            request_body = None

        permissions_value = op_item.get("x-permissions")
        permissions = permissions_value if isinstance(permissions_value, dict) else None
        required_roles = self._extract_required_roles(permissions)

        return OperationInfo(
            namespace=namespace,
            operation_id=operation_id,
            path=path,
            method=method.upper(),
            summary=summary,
            description=description,
            tags=[tag for tag in tags if isinstance(tag, str)],
            parameters=parameters,
            code_samples=[sample for sample in code_samples if isinstance(sample, dict)],
            request_body=request_body,
            permissions=permissions,
            required_roles=required_roles,
        )

    def _extract_parameters(
        self,
        op_item: dict[str, Any],
        path_item: dict[str, Any],
    ) -> list[ParameterInfo]:
        path_params = path_item.get("parameters")
        op_params = op_item.get("parameters")

        all_params: list[Any] = []
        if isinstance(path_params, list):
            all_params.extend(path_params)
        if isinstance(op_params, list):
            all_params.extend(op_params)

        extracted: list[ParameterInfo] = []
        seen: set[tuple[str, str]] = set()
        for value in all_params:
            if not isinstance(value, dict):
                continue
            if "$ref" in value:
                resolved = self._resolve_ref(value["$ref"])
                if resolved is None:
                    continue
                value = resolved
            name = value.get("name")
            location = value.get("in")
            if not isinstance(name, str) or not isinstance(location, str):
                continue
            key = (name, location)
            if key in seen:
                continue
            seen.add(key)
            schema_value = value.get("schema")
            schema = schema_value if isinstance(schema_value, dict) else {}
            description = value.get("description") if isinstance(value.get("description"), str) else None
            extracted.append(
                ParameterInfo(
                    name=name,
                    location=location,
                    required=bool(value.get("required", False)),
                    schema=schema,
                    description=description,
                )
            )
        return extracted

    def _resolve_ref(self, ref: Any) -> dict[str, Any] | None:
        """Resolve local refs under '#/components/*'."""
        if not isinstance(ref, str):
            return None
        if not ref.startswith("#/"):
            return None
        target: Any = self.spec
        for token in ref[2:].split("/"):
            if not isinstance(target, dict):
                return None
            target = target.get(token)
        return target if isinstance(target, dict) else None

    @staticmethod
    def _extract_required_roles(permissions: dict[str, Any] | None) -> list[str]:
        """Extract role names from x-permissions.roleList metadata."""
        if permissions is None:
            return []
        role_list = permissions.get("roleList")
        if not isinstance(role_list, list):
            return []
        roles: list[str] = []
        for entry in role_list:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if isinstance(name, str) and name.strip():
                roles.append(name.strip())
        # Keep ordering stable while removing duplicates.
        return list(dict.fromkeys(roles))
