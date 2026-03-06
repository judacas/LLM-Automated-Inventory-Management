"""ASGI app wrapper for the Inventory MCP server.

Why this file exists:
- Azure-friendly deployment: managed hosting expects an HTTP server.
- MCP support: The MCP Python SDK can serve MCP over "Streamable HTTP" under `/mcp`.

This module mounts the MCP server into a Starlette app and adds a simple `/health`
endpoint so we can validate the deployment quickly in Azure.
"""

import contextlib
from collections.abc import AsyncIterator

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from inventory_mcp.server import mcp


def _health(_request: Request) -> JSONResponse:
    """Lightweight health probe (not part of MCP spec)."""
    return JSONResponse({"status": "ok"})


@contextlib.asynccontextmanager
async def lifespan(_app: Starlette) -> AsyncIterator[None]:
    """Start/stop the MCP session manager with the ASGI app lifecycle."""
    async with mcp.session_manager.run():
        yield


app = Starlette(
    routes=[
        Route("/health", endpoint=_health, methods=["GET"]),
        Mount("/mcp", app=mcp.streamable_http_app()),
    ],
    lifespan=lifespan,
)
