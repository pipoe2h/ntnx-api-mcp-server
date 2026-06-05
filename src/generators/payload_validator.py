"""Server-side request payload validation against resolved OpenAPI schemas.

Validates the ``request_body`` passed to a namespace execute tool call before
the HTTP request is fired, returning structured field-level errors the LLM can
use to correct and retry without re-running discovery.
"""

from __future__ import annotations

from typing import Any


def validate_payload(
    payload: dict[str, Any],
    resolved_schema: dict[str, Any],
    path_prefix: str = "",
    max_errors: int = 5,
) -> list[dict[str, Any]]:
    """Validate a request payload dict against a resolved OpenAPI schema.

    Checks are applied in order:
    1. Required fields present (skipping ``readOnly`` fields — the API manages them).
    2. No unknown fields (``$``-prefixed keys and ``links`` are silently allowed
       since they are gateway metadata that may appear in GET responses).
    3. Type correctness for each provided field.
    4. Enum value validity when the schema defines an enum.
    5. Recursive validation for nested objects and array items.

    Args:
        payload: The request body dict provided by the LLM.
        resolved_schema: The fully resolved schema dict (from ``schema_resolver``).
        path_prefix: Dot-notation prefix for nested field paths in error messages.
        max_errors: Maximum number of errors to collect before stopping.

    Returns:
        A list of field-level error dicts. Empty list means the payload is valid.
        Each error dict contains ``field`` (dot-notation path), ``error`` (type),
        and additional context keys depending on the error type.
    """
    errors: list[dict[str, Any]] = []
    properties = resolved_schema.get("properties", {})
    required_fields = resolved_schema.get("required", [])

    # 1. Required fields — skip readOnly ones (API populates them server-side).
    for field in required_fields:
        if field not in payload:
            prop_meta = properties.get(field, {})
            if prop_meta.get("readOnly"):
                continue
            field_path = f"{path_prefix}.{field}" if path_prefix else field
            errors.append({
                "field": field_path,
                "error": "required field missing",
                "expected_type": prop_meta.get("type", "unknown"),
                "description": prop_meta.get("description", ""),
            })
            if len(errors) >= max_errors:
                return errors

    # 2–5. Provided field checks.
    for key, value in payload.items():
        field_path = f"{path_prefix}.{key}" if path_prefix else key

        if key not in properties:
            # Gateway metadata ($reserved, $objectType at top level, links) — pass silently.
            if key.startswith("$") or key == "links":
                continue
            errors.append({"field": field_path, "error": "unknown field"})
            if len(errors) >= max_errors:
                return errors
            continue

        prop_meta = properties[key]
        expected_type = prop_meta.get("type")

        if expected_type and value is not None:
            if not _check_type(value, expected_type):
                errors.append({
                    "field": field_path,
                    "error": "type mismatch",
                    "provided": type(value).__name__,
                    "expected_type": expected_type,
                    "description": prop_meta.get("description", ""),
                })
                if len(errors) >= max_errors:
                    return errors
                continue

        if "enum" in prop_meta and value not in prop_meta["enum"]:
            errors.append({
                "field": field_path,
                "error": "invalid enum value",
                "provided": value,
                "allowed_values": prop_meta["enum"],
            })
            if len(errors) >= max_errors:
                return errors

        if expected_type == "object" and isinstance(value, dict) and "properties" in prop_meta:
            nested = validate_payload(value, prop_meta, field_path, max_errors - len(errors))
            errors.extend(nested)
            if len(errors) >= max_errors:
                return errors

        if expected_type == "array" and isinstance(value, list):
            items_schema = prop_meta.get("items", {})
            if items_schema.get("type") == "object" and "properties" in items_schema:
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        nested = validate_payload(
                            item, items_schema,
                            f"{field_path}[{i}]",
                            max_errors - len(errors),
                        )
                        errors.extend(nested)
                        if len(errors) >= max_errors:
                            return errors

    return errors


def _check_type(value: Any, expected_type: str) -> bool:
    """Return True if ``value`` matches the given JSON Schema ``type`` string.

    Special cases:
    - ``integer`` explicitly rejects ``bool`` (Python's bool is a subclass of int).
    - ``number`` accepts both int and float.
    - Unknown type strings are treated as always-valid to avoid false positives.

    Args:
        value: The value to type-check.
        expected_type: A JSON Schema type string (``string``, ``integer``, etc.).
    """
    type_map: dict[str, type | tuple[type, ...]] = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    expected = type_map.get(expected_type)
    if expected is None:
        return True
    if expected_type == "integer" and isinstance(value, bool):
        return False
    return isinstance(value, expected)
