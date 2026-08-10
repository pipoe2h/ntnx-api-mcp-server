"""MCP Streamable HTTP runtime server entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from src.config import Settings
from src.mcp_stdio_server import build_mcp_server


def create_http_app(settings: Settings) -> Starlette:
    """Create an ASGI application exposing MCP at ``/mcp``."""
    server, _ = build_mcp_server(settings)
    session_manager = StreamableHTTPSessionManager(server, stateless=True)

    class MCPApplication:
        async def __call__(self, scope, receive, send) -> None:  # type: ignore[no-untyped-def]
            await session_manager.handle_request(scope, receive, send)

    async def health_endpoint(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    return Starlette(
        routes=[
            Route("/mcp", MCPApplication(), methods=["GET", "POST", "DELETE"]),
            Route("/health", health_endpoint, methods=["GET"]),
        ],
        lifespan=lifespan,
    )


def serve_http(settings: Settings, host: str, port: int) -> None:
    """Run the Streamable HTTP server until terminated."""
    uvicorn.run(create_http_app(settings), host=host, port=port)
