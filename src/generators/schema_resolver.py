"""Lazy recursive OpenAPI $ref / allOf / oneOf schema resolver."""

from __future__ import annotations

from typing import Any

# Sentinel values injected by Nutanix code-gen; never valid in API payloads.
_SENTINEL_ENUM_VALUES: frozenset[str] = frozenset({"$UNKNOWN", "$REDACTED"})


class SchemaResolver:
    """Resolve OpenAPI component schemas lazily with in-memory caching.

    Resolution is triggered on demand (e.g. when getOperationSchema is called)
    so startup latency is unaffected. Results are cached by ref name.

    Handles:
    - ``$ref``         → look up in combined components/schemas dict
    - ``allOf``        → merge all branch property maps
    - ``oneOf``/``anyOf`` → produce discriminator-keyed variant list
    - ``array``        → resolve items schema recursively
    - ``object``       → resolve each property recursively
    - primitives       → compact type/format/enum metadata

    ``readOnly`` fields that are complex (arrays, objects) are filtered from
    ``properties`` to reduce noise (e.g. HATEOAS ``links``).  Primitive
    ``readOnly`` fields (``string``, ``integer``, ``boolean``) are kept and
    marked ``readOnly: true`` so the LLM can echo them in PUT payloads and
    derive ``immutable_fields`` from the top-level schema.
    """

    def __init__(self, schemas: dict[str, dict[str, Any]]) -> None:
        self.schemas = schemas
        self._cache: dict[str, Any] = {}

    def resolve(
        self,
        schema: dict[str, Any],
        seen: frozenset[str] | None = None,
    ) -> dict[str, Any]:
        """Recursively resolve a schema node and return a compact representation."""
        if seen is None:
            seen = frozenset()

        if not isinstance(schema, dict):
            return {}

        # --- $ref ----------------------------------------------------------
        if "$ref" in schema:
            ref: str = schema["$ref"]
            ref_name = ref.split("/")[-1]
            if ref_name in self._cache:
                return self._cache[ref_name]
            if ref_name in seen:
                return {"type": "object", "_circular_ref": ref_name}
            target = self.schemas.get(ref_name)
            if target is None:
                return {"type": "object", "_unknown_ref": ref_name}
            result = self.resolve(target, seen | {ref_name})
            self._cache[ref_name] = result
            return result

        # --- allOf ---------------------------------------------------------
        if "allOf" in schema:
            merged_props: dict[str, Any] = {}
            merged_required: list[str] = []
            for branch in schema["allOf"]:
                resolved_branch = self.resolve(branch, seen)
                # Later branches overwrite earlier ones (standard allOf semantics).
                # Properties include primitive readOnly fields; complex readOnly are pre-filtered.
                merged_props.update(resolved_branch.get("properties", {}))
                merged_required.extend(resolved_branch.get("required", []))
            # Own-level properties have highest precedence
            for name, field_schema in schema.get("properties", {}).items():
                merged_props[name] = self._resolve_field(field_schema, seen)
            merged_required.extend(schema.get("required", []))
            out: dict[str, Any] = {
                "type": "object",
                "properties": {k: v for k, v in merged_props.items() if not _is_readonly_complex(v)},
                "required": list(dict.fromkeys(merged_required)),
            }
            if schema.get("deprecated"):
                out["deprecated"] = True
            return out

        # --- oneOf / anyOf -------------------------------------------------
        if "oneOf" in schema or "anyOf" in schema:
            branches: list[Any] = schema.get("oneOf") or schema.get("anyOf")  # type: ignore[assignment]
            disc_prop = (schema.get("discriminator") or {}).get("propertyName", "$objectType")
            variants: list[dict[str, Any]] = []
            for branch in branches:
                resolved_branch = self.resolve(branch, seen)
                branch_props = resolved_branch.get("properties", {})
                # Derive discriminator value from the enum on that field
                disc_enum = (branch_props.get(disc_prop) or {}).get("enum", [])
                when: str = disc_enum[0] if disc_enum else branch.get("$ref", "").split("/")[-1]
                variants.append({
                    "when": when,
                    "fields": {k: v for k, v in branch_props.items() if not _is_readonly_complex(v)},
                })
            out = {
                "type": "oneOf",
                "discriminator_field": disc_prop,
                "variants": variants,
            }
            # required at the oneOf level (e.g. [$objectType] discriminator field)
            if schema.get("required"):
                out["required"] = schema["required"]
            if schema.get("deprecated"):
                out["deprecated"] = True
            return out

        # --- array ---------------------------------------------------------
        if schema.get("type") == "array":
            result_arr: dict[str, Any] = {"type": "array"}
            for key in ("maxItems", "minItems"):
                if key in schema:
                    result_arr[key] = schema[key]
            items = schema.get("items")
            if items:
                result_arr["items"] = self.resolve(items, seen)
            if schema.get("deprecated"):
                result_arr["deprecated"] = True
            return result_arr

        # --- object with properties ----------------------------------------
        if schema.get("type") == "object" or "properties" in schema:
            required = schema.get("required", [])
            all_props = {
                name: self._resolve_field(field_schema, seen)
                for name, field_schema in schema.get("properties", {}).items()
            }
            out = {
                "type": "object",
                "properties": {k: v for k, v in all_props.items() if not _is_readonly_complex(v)},
                "required": required,
            }
            if schema.get("deprecated"):
                out["deprecated"] = True
            return out

        # --- primitive leaf ------------------------------------------------
        return _primitive_meta(schema)

    def _resolve_field(
        self, field_schema: dict[str, Any], seen: frozenset[str]
    ) -> dict[str, Any]:
        """Resolve a single property's schema node.

        For complex types (array / allOf / oneOf / $ref), ``resolve()`` is called
        on the field schema.  Any ``readOnly`` or ``deprecated`` annotation on the
        *field declaration itself* is then re-applied to the resolved result because
        the handlers for array/object/allOf do not copy those outer-level flags.
        """
        if not isinstance(field_schema, dict):
            return {}
        if "$ref" in field_schema or field_schema.get("type") == "array" or (
            "allOf" in field_schema or "oneOf" in field_schema or "anyOf" in field_schema
        ):
            resolved = self.resolve(field_schema, seen)
            # Propagate field-level annotations that the inner handlers don't carry
            if field_schema.get("readOnly"):
                resolved = {**resolved, "readOnly": True}
            if field_schema.get("deprecated"):
                resolved = {**resolved, "deprecated": True}
            return resolved
        return _primitive_meta(field_schema)


def _is_readonly_complex(field: Any) -> bool:
    """True for readOnly fields that are arrays or non-primitive objects (e.g. HATEOAS links).

    Primitive readOnly fields (string/integer/boolean) are intentionally kept
    visible so reference ``extId`` values and server-set identifiers remain
    accessible to the LLM for PUT echo-back and entity referencing.
    """
    if not isinstance(field, dict) or not field.get("readOnly"):
        return False
    field_type = field.get("type")
    # Keep primitive readOnly fields; filter complex ones to reduce noise
    return field_type not in ("string", "integer", "number", "boolean")


def _primitive_meta(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a compact metadata dict for a primitive-type schema node."""
    result: dict[str, Any] = {}
    for key in (
        "type", "format", "readOnly", "deprecated", "nullable",
        "pattern", "default", "minimum", "maximum",
        "maxLength", "minLength", "maxItems", "minItems",
    ):
        val = schema.get(key)
        if val is None:
            continue
        # Guard against non-JSON-serializable values (e.g. datetime in spec examples)
        if hasattr(val, "isoformat"):
            val = str(val)
        result[key] = val
    if "enum" in schema:
        # Strip internal code-gen sentinels — never valid in API payloads
        cleaned = [v for v in schema["enum"] if v not in _SENTINEL_ENUM_VALUES]
        result["enum"] = cleaned
    return result
