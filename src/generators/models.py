"""Pydantic contracts for tool and discovery payloads."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolInputSchema(BaseModel):
    """JSON schema payload used by MCP tool definitions."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    type: Literal["object"] = "object"
    properties: dict[str, dict[str, Any]] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)
    additional_properties: bool = Field(default=False, alias="additionalProperties")


class ToolAnnotations(BaseModel):
    """MCP 2025-03-26 tool hint vocabulary — clients use these for confirmation UX."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    readOnlyHint: bool | None = None
    destructiveHint: bool | None = None
    idempotentHint: bool | None = None
    openWorldHint: bool | None = None


class ToolDefinition(BaseModel):
    """Top-level MCP tool contract."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str
    description: str
    input_schema: ToolInputSchema = Field(alias="inputSchema")
    annotations: ToolAnnotations | None = None
    metadata: dict[str, Any] | None = None


class OperationDiscoveryItem(BaseModel):
    """Normalized discovery listing item."""

    model_config = ConfigDict(extra="forbid")

    namespace: str
    operation: str
    method: str
    path: str
    summary: str
    permission_name: str | None = None
    required_roles: list[str] = Field(default_factory=list)
    # Populated when a search term is provided; None when listing without search.
    relevance_score: int | None = None
    # Fields where the search tokens were matched; helps LLM assess match quality.
    match_fields: list[str] = Field(default_factory=list)
    # Original operation_id from the Nutanix spec when a collision required renaming.
    # None for the majority of operations where operation == spec operation_id.
    spec_operation_id: str | None = None
    # Discriminator prefix that was applied, e.g. 'ahv', 'esxi', 'installer'.
    # None when the operation has no variants in its namespace.
    path_variant: str | None = None
