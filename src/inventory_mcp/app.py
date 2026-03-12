"""ASGI app wrapper for the Inventory MCP server.

Why this file exists:
- Azure-friendly deployment: managed hosting expects an HTTP server.
- MCP support: The MCP Python SDK can serve MCP over "Streamable HTTP" under `/mcp`.

This module mounts the MCP server into a Starlette app and adds a simple `/health`
endpoint so we can validate the deployment quickly in Azure.
"""

import contextlib
import os
from collections.abc import AsyncIterator
from typing import Any, Awaitable, Callable

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from inventory_mcp.server import mcp

# Starlette's `Mount("/mcp", ...)` strips the mount prefix.
#
# For a request to exactly `/mcp` (no trailing slash), the mounted child app may
# receive an empty path (""), while most ASGI apps expect `scope["path"]` to be
# a non-empty string starting with `/`.
#
# In practice, some clients (including simple curl checks or certain HTTP libs)
# will hit `/mcp` (no trailing slash). If the child MCP transport sees an empty
# path, it may terminate the session during initialize.
#
# This wrapper normalizes that edge case so both `/mcp` and `/mcp/` behave.
_mcp_http_app = mcp.streamable_http_app()


async def _mcp_http_app_with_normalized_path(
    scope: dict[str, Any],
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    if scope.get("type") == "http":
        path = scope.get("path", "")

        # Normalize edge cases so clients can use either `/mcp` or `/mcp/`.
        # (Some UIs and tools are inconsistent about the trailing slash.)
        if path == "":
            scope = dict(scope)
            scope["path"] = "/"
        elif path == "/mcp/":
            scope = dict(scope)
            scope["path"] = "/mcp"
    await _mcp_http_app(scope, receive, send)


def _health(_request: Request) -> JSONResponse:
    """Lightweight health probe (not part of MCP spec)."""
    return JSONResponse({"status": "ok"})


@contextlib.asynccontextmanager
async def lifespan(_app: Starlette) -> AsyncIterator[None]:
    """Start/stop the MCP session manager with the ASGI app lifecycle."""
    async with mcp.session_manager.run():
        yield


app = Starlette(
    # CORS matters for the MCP Inspector UI.
    #
    # Why:
    # - `npx @modelcontextprotocol/inspector` serves a browser UI on (usually) http://localhost:5173.
    # - That UI then calls your MCP endpoint at http://localhost:8000/mcp.
    # - Different ports = different origin, and browsers will block the request unless we allow it.
    #
    # Configuration:
    # - Set `MCP_CORS_ORIGINS` to a comma-separated list of allowed origins.
    #   Example: "http://localhost:5173,http://127.0.0.1:5173"
    # - Or set it to "*" to allow any origin (OK for local demos; not recommended for production).
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=(
                ["*"]
                if os.getenv("MCP_CORS_ORIGINS", "").strip() == "*"
                else [
                    o.strip()
                    for o in os.getenv(
                        "MCP_CORS_ORIGINS",
                        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
                    ).split(",")
                    if o.strip()
                ]
            ),
            allow_methods=["*"],
            allow_headers=["*"],
        )
    ],
    routes=[
        # Traditional HTTP health probe (useful for Azure/App Service health checks).
        Route("/health", endpoint=_health, methods=["GET"]),
        # The MCP Streamable HTTP transport defines its own HTTP routes.
        # In particular, it serves the MCP endpoint at `/mcp`.
        #
        # Therefore we mount it at `/` so `/mcp` resolves correctly.
        # Example: http://localhost:8000/mcp
        Mount("/", app=_mcp_http_app_with_normalized_path),
    ],
    lifespan=lifespan,
)
