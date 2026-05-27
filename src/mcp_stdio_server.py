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
    """Convert internal tool definition to MCP SDK Tool model."""
    return types.Tool(
        name=definition["name"],
        description=definition.get("description"),
        inputSchema=definition.get("inputSchema", {"type": "object", "properties": {}}),
        _meta=definition.get("metadata"),
    )


def _build_instructions(namespaces: list[str]) -> str:
    """Build the MCP instructions field dynamically from loaded namespaces."""
    ns_routing = ", ".join(f'"{ns}" -> {ns}_execute' for ns in sorted(namespaces))

    return (
        "NUTANIX V4 API MCP SERVER - DISCOVERY PROTOCOL\n\n"
        "NORMAL PATH (always follow this sequence):\n"
        "1. Call listOperations(search='<1-2 keyword tokens>') - returns ranked results.\n"
        "2. Position 1 is the server's highest-confidence match.\n"
        "3. Check relevance_score and match_fields:\n"
        "   - match_fields containing 'operation_id' = strong match, proceed with confidence.\n"
        "   - match_fields containing only 'search_text' = weak match, try a different keyword.\n"
        "4. Call getOperationSchema(operation='<operation>') to confirm parameters.\n"
        "5. Call {namespace}_execute(operation='<operation>', ...) using the EXACT\n"
        "   namespace and operation values from the listOperations result.\n\n"
        "VARIANT OPERATIONS:\n"
        "Some operations exist in multiple path variants (e.g. AHV vs ESXi hypervisors).\n"
        "These are registered as '{discriminator}_{operationId}', e.g. 'ahv_listVms' and\n"
        "'esxi_listVms'. Each is a distinct, fully-addressable operation.\n"
        "- When path_variant is present in a listOperations result, that IS the operation to call.\n"
        "- spec_operation_id shows the original Nutanix spec name for reference only.\n"
        "- Default rule: prefer 'ahv_' variants for VMM operations when the cluster\n"
        "  hypervisor is not specified by the user.\n\n"
        "NAMESPACE ROUTING - GUARANTEED CONTRACT:\n"
        "The 'namespace' field in every listOperations result is the EXACT prefix of the\n"
        "correct execute tool. Never guess the tool name.\n"
        f"Loaded namespaces: {ns_routing}\n\n"
        "ZERO RESULTS PATH:\n"
        "If listOperations returns empty, your keyword uses vocabulary not in the spec.\n"
        "Retry once using abbreviated API-style terms (e.g. 'vm' not 'virtual machine',\n"
        "'dataprotection' not 'backup', 'clustermgmt' not 'cluster management').\n\n"
        "NEVER-GUESS RULE:\n"
        "Calling any {namespace}_execute with an operation not returned by listOperations\n"
        "will return unknown_operation. Always discover first."
    )


async def _serve_stdio(settings: Settings) -> None:
    dispatcher = build_runtime_dispatcher(settings)

    # Derive loaded namespaces for the dynamic instructions field.
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
    """Run the MCP stdio server until terminated."""
    asyncio.run(_serve_stdio(settings))
