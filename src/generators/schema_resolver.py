"""OpenAPI $ref and allOf resolution for runtime schema flattening.

This module resolves OpenAPI component schemas at call time — not at parse time —
so the server only pays the resolution cost when getOperationSchema is actually called.
It is used by ToolGenerator to surface request_body_schema with real field types
(including correct enum values) rather than unresolvable $ref pointers.
"""

from __future__ import annotations

from typing import Any


# Keys preserved verbatim when a schema node is a scalar type.
# Anything not in this set (e.g. 'x-internal', '$schema') is stripped.
_SCALAR_PRESERVE_KEYS: frozenset[str] = frozenset({
    "type", "enum", "format", "description",
    "minimum", "maximum", "default", "pattern",
    "minLength", "maxLength", "example",
    "x-enumDescriptions", "readOnly",
})

# JSON Schema primitive types that should NOT be wrapped as objects.
_SCALAR_TYPES: frozenset[str] = frozenset({"string", "integer", "number", "boolean"})


def resolve_request_body_schema(
    raw_request_body: dict[str, Any],
    component_schemas: dict[str, Any],
) -> dict[str, Any] | None:
    """Resolve the request body schema from a raw OpenAPI requestBody object.

    Extracts the application/json schema, follows any top-level $ref, and
    returns a fully resolved properties map the LLM can use to construct payloads.

    Args:
        raw_request_body: The raw ``requestBody`` dict from the OpenAPI operation.
        component_schemas: The ``#/components/schemas`` dict from the same YAML.

    Returns:
        A resolved schema dict with ``properties`` and ``required``, or ``None``
        if no application/json schema is present.
    """
    content = raw_request_body.get("content", {})
    json_schema = content.get("application/json", {}).get("schema")
    if not json_schema:
        return None
    return _resolve_schema(json_schema, component_schemas, frozenset())


def _resolve_ref(
    ref: str,
    component_schemas: dict[str, Any],
    visited: frozenset[str],
) -> dict[str, Any]:
    """Resolve a single local $ref string to its schema dict.

    Tracks visited schema names to detect and break circular references,
    returning ``{"$circular": name}`` as a sentinel when a cycle is found.

    Args:
        ref: The raw $ref string (e.g. ``#/components/schemas/Foo``).
        component_schemas: Full components/schemas lookup dict.
        visited: Set of schema names already on the current resolution path.
    """
    name = ref.replace("#/components/schemas/", "")
    if name in visited:
        return {"$circular": name}
    return _resolve_schema(
        component_schemas.get(name, {}),
        component_schemas,
        visited | {name},
    )


def _resolve_schema(
    schema: dict[str, Any],
    component_schemas: dict[str, Any],
    visited: frozenset[str],
) -> dict[str, Any]:
    """Recursively resolve a single schema node, following $ref and allOf.

    Resolution rules (applied in order):
    - If the node has ``$ref``: delegate to ``_resolve_ref``.
    - If the node is a scalar type (string/integer/number/boolean) with no
      allOf: return it as-is, preserving only ``_SCALAR_PRESERVE_KEYS``.
    - If the node has ``allOf``: merge properties and required lists from all parts.
    - For each property:
      - $ref → resolve and flatten; if scalar, preserve enum/type directly.
      - array with $ref items → resolve items schema.
      - oneOf/anyOf (polymorphic discriminator) → resolve each variant and
        attach as ``subtypes`` list for LLM visibility.
      - Otherwise: pass through unchanged.

    Args:
        schema: The schema node to resolve.
        component_schemas: Full components/schemas lookup dict.
        visited: Schema names already visited on this resolution path.

    Returns:
        A dict with ``type``, ``properties``, ``required``, and optionally
        ``readOnly`` preserved from the source schema.
    """
    if "$ref" in schema:
        return _resolve_ref(schema["$ref"], component_schemas, visited)

    schema_type = schema.get("type")

    # Scalar — return with preserved constraints, no property expansion needed.
    if schema_type in _SCALAR_TYPES and "allOf" not in schema:
        return {k: v for k, v in schema.items() if k in _SCALAR_PRESERVE_KEYS}

    result: dict[str, Any] = {}
    required: list[str] = list(schema.get("required", []))

    if "allOf" in schema:
        for part in schema["allOf"]:
            resolved_part = _resolve_schema(part, component_schemas, visited)
            result.update(resolved_part.get("properties", {}))
            required.extend(resolved_part.get("required", []))
    else:
        result.update(schema.get("properties", {}))

    resolved_props: dict[str, Any] = {}
    for prop_name, prop_schema in result.items():
        resolved_props[prop_name] = _resolve_property(
            prop_name, prop_schema, component_schemas, visited
        )

    result_schema: dict[str, Any] = {
        "type": schema.get("type", "object"),
        "properties": resolved_props,
        "required": list(dict.fromkeys(required)),
    }
    if schema.get("readOnly"):
        result_schema["readOnly"] = True
    return result_schema


def _resolve_property(
    prop_name: str,
    prop_schema: Any,
    component_schemas: dict[str, Any],
    visited: frozenset[str],
) -> Any:
    """Resolve a single property schema within a parent object.

    Handles the four cases that require special treatment:
    - ``$ref`` property: resolve and flatten, distinguishing scalar from object.
    - ``array`` with ``$ref`` items: resolve the item schema.
    - ``oneOf`` / ``anyOf`` (polymorphic): resolve each subtype and attach as
      ``subtypes`` for discriminator visibility.
    - Anything else: pass through unchanged.

    Args:
        prop_name: Property name (used only for context, not for logic).
        prop_schema: The raw property schema dict (or any value).
        component_schemas: Full components/schemas lookup dict.
        visited: Schema names already on the current resolution path.

    Returns:
        The resolved property schema dict.
    """
    if not isinstance(prop_schema, dict):
        return prop_schema

    if "$ref" in prop_schema:
        sub = _resolve_ref(prop_schema["$ref"], component_schemas, visited)
        actual_type = sub.get("type", "object")
        if actual_type in _SCALAR_TYPES:
            # Enum/scalar behind a $ref — return the actual type with constraints.
            entry: dict[str, Any] = {"type": actual_type}
            desc = sub.get("description") or prop_schema.get("description", "")
            if desc:
                entry["description"] = desc
            for key in ("enum", "format", "minimum", "maximum", "default", "pattern", "readOnly"):
                if key in sub:
                    entry[key] = sub[key]
            return entry
        obj_entry: dict[str, Any] = {
            "type": "object",
            "description": prop_schema.get("description", ""),
            "properties": sub.get("properties", {}),
            "required": sub.get("required", []),
        }
        if sub.get("readOnly") or prop_schema.get("readOnly"):
            obj_entry["readOnly"] = True
        return obj_entry

    if prop_schema.get("type") == "array" and isinstance(prop_schema.get("items"), dict):
        items = prop_schema["items"]
        if "$ref" in items:
            sub = _resolve_ref(items["$ref"], component_schemas, visited)
            actual_item_type = sub.get("type", "object")
            if actual_item_type in _SCALAR_TYPES:
                return {
                    "type": "array",
                    "description": prop_schema.get("description", ""),
                    "items": {k: sub[k] for k in ("type", "enum", "format", "description") if k in sub},
                }
            return {
                "type": "array",
                "description": prop_schema.get("description", ""),
                "items": {"type": "object", "properties": sub.get("properties", {})},
            }
        return prop_schema

    # Polymorphic discriminator field (e.g. bootConfig with oneOf LegacyBoot/UefiBoot).
    if "oneOf" in prop_schema or "anyOf" in prop_schema:
        variants_key = "oneOf" if "oneOf" in prop_schema else "anyOf"
        subtypes = [
            _resolve_ref(v["$ref"], component_schemas, visited)
            for v in prop_schema[variants_key]
            if "$ref" in v
        ]
        inline = {k: v for k, v in prop_schema.items() if k not in (variants_key, "$ref")}
        inline["subtypes"] = subtypes
        return inline

    return prop_schema
