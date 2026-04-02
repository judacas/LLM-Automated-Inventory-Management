"""ASGI wrapper for the mock auth MCP server."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from mock_auth_mcp.server import mcp

_mcp_http_app: ASGIApp = mcp.streamable_http_app()

_session_manager_ready = asyncio.Event()
_session_manager_lock = asyncio.Lock()
_session_manager_task: asyncio.Task[None] | None = None


async def _ensure_session_manager_running() -> None:
    """Make sure the streamable HTTP session manager is alive."""

    global _session_manager_task
    if _session_manager_ready.is_set():
        return

    async with _session_manager_lock:
        if _session_manager_ready.is_set():
            return

        if _session_manager_task is None:

            async def _runner() -> None:
                async with mcp.session_manager.run():
                    _session_manager_ready.set()
                    await asyncio.Event().wait()

            _session_manager_task = asyncio.create_task(_runner())

    await _session_manager_ready.wait()


async def _mcp_http_app_with_normalized_path(
    scope: Scope, receive: Receive, send: Send
) -> None:
    """Normalize paths and start the session manager lazily."""

    await _ensure_session_manager_running()

    if scope.get("type") == "http":
        path = scope.get("path", "")
        if path == "":
            scope = dict(scope)
            scope["path"] = "/"
        elif path == "/mcp/":
            scope = dict(scope)
            scope["path"] = "/mcp"
    await _mcp_http_app(scope, receive, send)


def _health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def _cors_origins() -> list[str]:
    raw = os.getenv("MOCK_AUTH_MCP_CORS_ORIGINS", "")
    if raw.strip() == "*":
        return ["*"]
    if raw.strip():
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


async def lifespan(_: Starlette) -> AsyncIterator[None]:
    async with mcp.session_manager.run():
        _session_manager_ready.set()
        yield


app = Starlette(
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=_cors_origins(),
            allow_methods=["*"],
            allow_headers=["*"],
        )
    ],
    routes=[
        Route("/health", endpoint=_health, methods=["GET"]),
        Mount("/", app=_mcp_http_app_with_normalized_path),
    ],
    lifespan=lifespan,
)
