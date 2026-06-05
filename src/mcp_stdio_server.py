"""MCP stdio runtime server entrypoint."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp import types
from mcp.server import NotificationOptions
from mcp.server.lowlevel import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

from src.config import Settings
from src.server import build_runtime_dispatcher


def _to_mcp_tool(definition: dict[str, Any]) -> types.Tool:
    """Convert an internal tool definition dict to the MCP SDK Tool model."""
    return types.Tool(
        name=definition["name"],
        description=definition.get("description"),
        inputSchema=definition.get("inputSchema", {"type": "object", "properties": {}}),
        _meta=definition.get("metadata"),
    )


def _build_instructions(namespaces: list[str]) -> str:
    """Build the MCP instructions field from the set of loaded namespaces.

    The instructions encode the complete discovery protocol the LLM must follow,
    including ranked search, variant routing, path parameter conventions,
    and the mandatory GET-before-PUT workflow for full-replacement APIs.

    Args:
        namespaces: Sorted list of namespace identifiers loaded at startup.
    """
    ns_routing = ", ".join(f'"{ns}" -> {ns}_execute' for ns in sorted(namespaces))

    return (
        "NUTANIX V4 API MCP SERVER - DISCOVERY PROTOCOL\n\n"

        "NORMAL PATH (always follow this sequence):\n"
        "1. Call listOperations(search='<1-2 keyword tokens>') — returns ranked results.\n"
        "2. Position 1 is the server's highest-confidence match.\n"
        "3. Check relevance_score and match_fields:\n"
        "   - 'operation_id' in match_fields = strong signal, proceed.\n"
        "   - 'search_text' only = weak signal, try a different keyword.\n"
        "4. Call getOperationSchema(operation='<operation>') to confirm parameters.\n"
        "   - 'parameter_summary' lists path/query params (e.g. extId) to pass as\n"
        "     top-level keyword arguments in the execute call.\n"
        "   - 'request_body_schema' shows resolved field types for POST/PUT bodies.\n"
        "   - 'immutable_fields' lists readOnly fields that must be echoed back\n"
        "     unchanged in PUT bodies.\n"
        "5. Call {namespace}_execute(operation='<operation>', ...) using the EXACT\n"
        "   namespace and operation values from the listOperations result.\n"
        "   - Pass path parameters (e.g. extId='abc-123') as top-level keyword args.\n"
        "   - Pass the request body for POST/PUT/PATCH as 'request_body'.\n\n"

        "VARIANT OPERATIONS:\n"
        "Some operations exist in multiple path variants (e.g. for different hypervisors).\n"
        "These are registered as '{discriminator}_{operationId}' (e.g. 'ahv_listVms',\n"
        "'esxi_listVms'). Each variant is fully addressable.\n"
        "- 'path_variant' in a listOperations result identifies the discriminator.\n"
        "- 'spec_operation_id' shows the original API spec name for reference.\n"
        "- When hypervisor is not specified, prefer the AHV variant for VMM operations.\n\n"

        "NAMESPACE ROUTING:\n"
        "The 'namespace' field in every listOperations result is the EXACT prefix of\n"
        "the correct execute tool. Never guess the tool name.\n"
        f"Loaded namespaces: {ns_routing}\n\n"

        "ZERO RESULTS:\n"
        "If listOperations returns empty, your keyword may not match the API spec vocabulary.\n"
        "Retry with abbreviated, API-style terms rather than natural language phrases.\n"
        "Inspect the loaded namespace list above for naming conventions.\n\n"

        "PUT OPERATIONS — MANDATORY WORKFLOW:\n"
        "Nutanix PUT replaces the entire resource. Missing fields are set to null.\n"
        "Always follow this sequence:\n"
        "1. getOperationSchema → note immutable_fields and parameter_summary.\n"
        "2. GET the current resource using the path parameter (e.g. extId).\n"
        "3. Start with the complete GET response body.\n"
        "4. Remove keys starting with '$' and 'links' (response-only gateway metadata).\n"
        "5. Keep all immutable_fields — echo them back unchanged. Do not modify them.\n"
        "6. Apply only your intended change.\n"
        "7. PUT the full modified body. Never send a partial body for PUT.\n\n"

        "NEVER-GUESS RULE:\n"
        "Calling any {namespace}_execute with an operation not returned by listOperations\n"
        "will return unknown_operation. Always discover first."
    )


async def _serve_stdio(settings: Settings) -> None:
    """Start the async MCP stdio server and run until the client disconnects."""
    dispatcher = build_runtime_dispatcher(settings)

    loaded_namespaces = sorted({op.namespace for op in dispatcher.generator.operations})
    server = Server(
        name="nutanix-v4-mcp-server",
        version="0.1.0",
        instructions=_build_instructions(loaded_namespaces),
    )

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return [_to_mcp_tool(tool) for tool in dispatcher.list_tools()]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> types.CallToolResult | dict[str, Any]:
        result = dispatcher.call_tool(name, arguments)
        if result.ok:
            return result.as_dict()
        return types.CallToolResult(
            isError=True,
            content=[
                types.TextContent(
                    type="text",
                    text=json.dumps(result.as_dict(), indent=2),
                )
            ],
            structuredContent=result.as_dict(),
        )

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="nutanix-v4-mcp-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def serve_stdio(settings: Settings) -> None:
    """Run the MCP stdio server until terminated by the client."""
    asyncio.run(_serve_stdio(settings))
