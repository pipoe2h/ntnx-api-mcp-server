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


async def _serve_stdio(settings: Settings) -> None:
    dispatcher = build_runtime_dispatcher(settings)
    server = Server(
        name="nutanix-v4-mcp-server",
        version="0.1.0",
        instructions=(
            "Nutanix V4 API MCP server exposing namespace execute and discovery tools. "
            "Use listOperations/getOperationSchema/getCodeSample before executing operations."
        ),
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
