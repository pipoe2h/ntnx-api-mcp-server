"""OpenAPI YAML parser for operation extraction."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import logging
import re
from pathlib import Path
from typing import Any

import yaml

LOGGER = logging.getLogger(__name__)

_VERSION_SEG_RE = re.compile(r"^v\d+", re.IGNORECASE)


@dataclass(slots=True)
class NamespaceMetadata:
    """Display metadata derived from the OpenAPI ``info`` block and root tags list."""

    namespace: str
    title: str
    description: str
    categories: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ParameterInfo:
    """Operation parameter metadata."""

    name: str
    location: str
    required: bool
    schema: dict[str, Any] = field(default_factory=dict)
    description: str | None = None
    odata_fields: list[str] = field(default_factory=list)


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
    # Pre-built enriched text blob for ranked search (built at parse time).
    search_text: str = field(default="")
    # Unique name used in enums, index keys, and execute calls.
    # Equals operation_id for non-colliding ops; '{discriminator}_{operation_id}' for variants.
    registered_name: str = field(default="")
    # The discriminator segment that was prefixed, e.g. 'ahv', 'esxi', 'installer'.
    # None when there is no collision for this operation_id within its namespace.
    path_variant: str | None = field(default=None)

    def __post_init__(self) -> None:
        # Ensure registered_name always has a value even when built without collision detection.
        if not self.registered_name:
            self.registered_name = self.operation_id


def _camel_to_tokens(name: str) -> str:
    """Split camelCase/PascalCase into space-separated lowercase tokens.

    listRecoveryPoints  -> 'list recovery points'
    getVmAntiAffinityPolicy -> 'get vm anti affinity policy'
    """
    return re.sub(r"([A-Z])", r" \1", name).strip().lower()


def _path_to_tokens(path: str) -> str:
    """Extract meaningful tokens from an API path.

    /dataprotection/v4.0/config/recovery-points/{extId}
    -> 'dataprotection config recovery points'
    """
    meaningful: list[str] = []
    for seg in path.split("/"):
        seg = seg.strip()
        if not seg or seg.startswith("{") or _VERSION_SEG_RE.match(seg):
            continue
        meaningful.append(seg.replace("-", " ").replace("_", " ").lower())
    return " ".join(meaningful)


def _meaningful_path_segments(path: str) -> list[str]:
    """Return path segments excluding version strings, parameters, and empty parts."""
    return [
        seg for seg in path.split("/")
        if seg and not seg.startswith("{") and not _VERSION_SEG_RE.match(seg)
    ]


def _common_suffix_ci(strings: list[str]) -> str:
    """Return the longest common case-insensitive suffix shared by all strings."""
    if not strings:
        return ""
    lowered = [s.lower() for s in strings]
    shortest = min(lowered, key=len)
    suffix_len = 0
    for i in range(1, len(shortest) + 1):
        candidate = shortest[-i:]
        if all(s.endswith(candidate) for s in lowered):
            suffix_len = i
        else:
            break
    return shortest[-suffix_len:] if suffix_len else ""


def _to_snake(text: str) -> str:
    """Convert PascalCase or mixed text to lowercase snake_case."""
    s = re.sub(r"([A-Z])", r"_\1", text).strip("_").lower()
    return re.sub(r"_+", "_", s)


def _derive_discriminators(variants: list[OperationInfo]) -> list[str]:
    """Derive a unique, stable discriminator label for each variant in a collision group.

    Priority per variant:
    1. Tag-based: strip the common suffix from all first-tags; if non-empty, use it.
    2. Path-based fallback: first unique meaningful path segment for that variant.
    3. Index fallback: 'variant_{n}' (should never be reached in practice).
    """
    first_tags = [op.tags[0] if op.tags else "" for op in variants]
    all_paths = [op.path for op in variants]

    # --- Tag-based discriminators ---
    common_sfx = _common_suffix_ci([t for t in first_tags if t])
    tag_discs: list[str | None] = []
    for tag in first_tags:
        if not tag:
            tag_discs.append(None)
            continue
        stripped = tag[: len(tag) - len(common_sfx)] if common_sfx else tag
        disc = _to_snake(stripped) if stripped else None
        tag_discs.append(disc)

    # --- Path-based discriminators ---
    seg_sets = [set(_meaningful_path_segments(p)) for p in all_paths]
    common_segs = seg_sets[0].intersection(*seg_sets[1:]) if len(seg_sets) > 1 else seg_sets[0]
    path_discs: list[str | None] = [
        next((s for s in sorted(segs - common_segs)), None) for segs in seg_sets
    ]

    # --- Merge: tag first, path as fallback ---
    merged = [
        (td if td else pd) for td, pd in zip(tag_discs, path_discs)
    ]

    # --- Uniqueness guarantee: if merge produced duplicates, fall back to pure path ---
    if len(set(merged)) < len(merged):
        merged = path_discs  # type: ignore[assignment]

    # --- Final fallback: positional index ---
    final: list[str] = [
        (m if m else f"variant_{i}") for i, m in enumerate(merged)
    ]

    # Ensure uniqueness even after all fallbacks (edge-case guard).
    if len(set(final)) < len(final):
        final = [f"variant_{i}" for i in range(len(variants))]

    return final


def resolve_collisions(operations: list[OperationInfo]) -> list[OperationInfo]:
    """Assign registered_name and path_variant for all operations in a namespace.

    Non-colliding operations: registered_name == operation_id, path_variant == None.
    Colliding operations: registered_name == '{discriminator}_{operation_id}',
                          path_variant == discriminator.
    Logs one WARNING per collision group at startup.
    """
    # Group by operation_id to find collisions.
    groups: dict[str, list[int]] = defaultdict(list)
    for idx, op in enumerate(operations):
        groups[op.operation_id].append(idx)

    for op_id, indices in groups.items():
        if len(indices) == 1:
            # No collision — registered_name already set to operation_id via __post_init__.
            continue

        variants = [operations[i] for i in indices]
        discriminators = _derive_discriminators(variants)

        LOGGER.warning(
            "Operation ID collision in namespace '%s': '%s' has %d variants. "
            "Registered names: %s",
            variants[0].namespace,
            op_id,
            len(variants),
            [f"{d}_{op_id}" for d in discriminators],
        )

        for idx_pos, disc in zip(indices, discriminators):
            op = operations[idx_pos]
            # dataclass with slots=True: must reassign, not mutate in place via setattr
            operations[idx_pos] = OperationInfo(
                namespace=op.namespace,
                operation_id=op.operation_id,
                path=op.path,
                method=op.method,
                summary=op.summary,
                description=op.description,
                tags=op.tags,
                parameters=op.parameters,
                code_samples=op.code_samples,
                request_body=op.request_body,
                permissions=op.permissions,
                required_roles=op.required_roles,
                search_text=op.search_text,
                registered_name=f"{disc}_{op_id}",
                path_variant=disc,
            )

    return operations


def _truncate_description(text: str, max_chars: int = 120) -> str:
    """Truncate description to the first sentence or ``max_chars`` characters."""
    if not text:
        return ""
    for sep in (".\n", ". ", "\n\n"):
        idx = text.find(sep)
        if 0 < idx < max_chars:
            return text[: idx + 1].strip()
    if len(text) <= max_chars:
        return text.strip()
    return text[:max_chars].rstrip() + "..."


class OpenAPIParser:
    """Parser for v4 OpenAPI YAML specifications."""

    SUPPORTED_METHODS = ("get", "post", "put", "patch", "delete")

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.spec: dict[str, Any] = {}
        # Populated by load() — keyed by component schema name.
        self.schemas: dict[str, Any] = {}

    def load(self) -> dict[str, Any]:
        """Load and return OpenAPI document, populating ``self.schemas``."""
        with self.file_path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
        if not isinstance(loaded, dict):
            raise ValueError(f"YAML root must be an object in {self.file_path}")
        self.spec = loaded
        components = self.spec.get("components")
        if isinstance(components, dict):
            raw_schemas = components.get("schemas")
            if isinstance(raw_schemas, dict):
                self.schemas = raw_schemas
        return self.spec

    def get_namespace_metadata(self, namespace: str) -> NamespaceMetadata:
        """Build display metadata from the spec ``info`` block and root tags list."""
        info = self.spec.get("info")
        info = info if isinstance(info, dict) else {}
        title = str(info.get("title") or namespace)
        raw_desc = info.get("description") or ""
        description = _truncate_description(str(raw_desc))

        categories: list[str] = []
        tags = self.spec.get("tags")
        if isinstance(tags, list):
            for tag in tags:
                if not isinstance(tag, dict):
                    continue
                display = tag.get("x-displayName") or tag.get("name")
                if isinstance(display, str) and display.strip():
                    categories.append(display.strip())

        return NamespaceMetadata(
            namespace=namespace,
            title=title,
            description=description,
            categories=categories,
        )

    def extract_operations(self, namespace: str) -> list[OperationInfo]:
        """Extract supported HTTP operations from OpenAPI paths."""
        if not self.spec:
            self.load()
        paths = self.spec.get("paths", {})
        if not isinstance(paths, dict):
            return []

        tag_descriptions = self._extract_tag_descriptions()

        operations: list[OperationInfo] = []
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method in self.SUPPORTED_METHODS:
                op_item = path_item.get(method)
                if not isinstance(op_item, dict):
                    continue
                operation = self._build_operation(
                    namespace, path, method, op_item, path_item, tag_descriptions
                )
                if operation is not None:
                    operations.append(operation)

        # Second pass: detect collisions and assign registered_name / path_variant.
        return resolve_collisions(operations)

    def extract_get_operations(self, namespace: str) -> list[OperationInfo]:
        """Backward-compatible helper for legacy tests/callers."""
        return [op for op in self.extract_operations(namespace) if op.method == "GET"]

    def _extract_tag_descriptions(self) -> dict[str, str]:
        """Build tag-name -> description map from root-level OpenAPI tags array."""
        result: dict[str, str] = {}
        tags = self.spec.get("tags")
        if not isinstance(tags, list):
            return result
        for tag in tags:
            if not isinstance(tag, dict):
                continue
            name = tag.get("name")
            desc = tag.get("description")
            if isinstance(name, str) and name:
                result[name] = desc if isinstance(desc, str) else ""
        return result

    def _build_operation(
        self,
        namespace: str,
        path: str,
        method: str,
        op_item: dict[str, Any],
        path_item: dict[str, Any],
        tag_descriptions: dict[str, str],
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
        if not isinstance(code_samples_value, list):
            code_samples_value = op_item.get("x-code-samples")
        code_samples = code_samples_value if isinstance(code_samples_value, list) else []

        request_body = op_item.get("requestBody")
        if not isinstance(request_body, dict):
            request_body = None

        permissions_value = op_item.get("x-permissions")
        permissions = permissions_value if isinstance(permissions_value, dict) else None
        required_roles = self._extract_required_roles(permissions)

        clean_tags = [tag for tag in tags if isinstance(tag, str)]
        search_text = self._build_search_text(
            operation_id=operation_id,
            path=path,
            summary=summary,
            description=description,
            tags=clean_tags,
            tag_descriptions=tag_descriptions,
        )

        # registered_name is set to operation_id here; resolve_collisions will update it.
        return OperationInfo(
            namespace=namespace,
            operation_id=operation_id,
            path=path,
            method=method.upper(),
            summary=summary,
            description=description,
            tags=clean_tags,
            parameters=parameters,
            code_samples=[s for s in code_samples if isinstance(s, dict)],
            request_body=request_body,
            permissions=permissions,
            required_roles=required_roles,
            search_text=search_text,
            registered_name=operation_id,
            path_variant=None,
        )

    @staticmethod
    def _build_search_text(
        operation_id: str,
        path: str,
        summary: str,
        description: str,
        tags: list[str],
        tag_descriptions: dict[str, str],
    ) -> str:
        """Build enriched searchable text for an operation."""
        parts: list[str] = [
            operation_id.lower(),
            summary.lower(),
            _camel_to_tokens(operation_id),
            _path_to_tokens(path),
        ]

        desc_lower = description.lower()
        if desc_lower != summary.lower():
            parts.append(desc_lower)

        for tag in tags:
            parts.append(tag.lower())
            parts.append(_camel_to_tokens(tag))
            tag_desc = tag_descriptions.get(tag, "")
            if tag_desc:
                parts.append(tag_desc.lower())

        return " ".join(parts)

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
            raw_odata = value.get("x-odata-fields")
            odata_fields = (
                [f["name"] for f in raw_odata if isinstance(f, dict) and "name" in f]
                if isinstance(raw_odata, list) else []
            )
            extracted.append(
                ParameterInfo(
                    name=name,
                    location=location,
                    required=bool(value.get("required", False)),
                    schema=schema,
                    description=description,
                    odata_fields=odata_fields,
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
        return list(dict.fromkeys(roles))
