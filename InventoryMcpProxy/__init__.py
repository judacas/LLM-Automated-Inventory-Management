"""Azure Functions HTTP trigger that forwards requests to our ASGI app.

Why this exists:
- Your project is built as a normal ASGI app (Starlette) for local dev via Uvicorn.
- Your team wants to demo using Azure Functions (Consumption/Y1) without containers.

How it works:
- Azure Functions invokes `main(req, context)` for every HTTP request.
- `func.AsgiMiddleware` adapts Azure Functions' HttpRequest/HttpResponse to ASGI.
- We forward all routes (see function.json route: "{*route}") to the ASGI app.

Important detail about imports (src/ layout):
- Your packages live under `src/`, so we add `./src` to `sys.path` at runtime.
  This avoids needing an editable install on Azure during the demo.
"""

from __future__ import annotations

import inspect
import os
import sys

import azure.functions as func

# Ensure `src/` packages (inventory_mcp, inventory_service, etc.) are importable.
REPO_ROOT = os.path.dirname(__file__)
SRC_PATH = os.path.join(REPO_ROOT, "..", "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

# Import the ASGI app we already use locally.
# This app exposes:
# - GET /health
# - MCP Streamable HTTP at /mcp
from inventory_mcp.app import app as asgi_app  # noqa: E402

# Create the Azure Functions -> ASGI adapter.
asgi_middleware = func.AsgiMiddleware(asgi_app)


async def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    """Azure Functions entrypoint."""

    # Delegate the entire request to the ASGI app.
    #
    # azure-functions has had a couple of adapter APIs over time. This shim makes
    # the demo resilient across versions.
    handler = (
        getattr(asgi_middleware, "handle_async", None)
        or getattr(asgi_middleware, "handle", None)
        or getattr(asgi_middleware, "main", None)
    )
    if handler is None:  # pragma: no cover
        raise RuntimeError(
            "azure.functions.AsgiMiddleware has no supported handler method"
        )

    result = handler(req, context)
    if inspect.isawaitable(result):
        return await result
    return result
