"""Pydantic contracts for tool and discovery payloads."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolInputSchema(BaseModel):
    """JSON schema payload used by MCP tool definitions."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["object"] = "object"
    properties: dict[str, dict[str, Any]] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)


class ToolDefinition(BaseModel):
    """Top-level MCP tool contract."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str
    description: str
    input_schema: ToolInputSchema = Field(alias="inputSchema")
    metadata: dict[str, Any] | None = None


class OperationDiscoveryItem(BaseModel):
    """Normalized discovery listing item."""

    model_config = ConfigDict(extra="forbid")

    namespace: str
    operation: str
    method: str
    path: str
    summary: str
