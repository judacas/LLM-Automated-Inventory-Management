"""ASGI app for the Admin Orchestrator.

This app is the bridge between the admin UI and the orchestrator logic.

Design goals (MVP):
- Provide a simple HTTP surface (`/health`, `/chat`) the frontend can call.
- Keep the core orchestration logic in `AdminOrchestratorService` so it stays
  unit-testable and reusable.

Notes:
- The orchestrator currently uses deterministic intent classification.
- Inventory data is fetched via MCP tools using `InventoryMcpClient`.
- Quote-agent/A2A integration is intentionally not implemented yet.
"""

from __future__ import annotations

import os

from fastapi import Body, FastAPI
from starlette.middleware.cors import CORSMiddleware

from admin_orchestrator_agent.service import AdminOrchestratorService


def _parse_cors_origins(env_value: str) -> list[str]:
    """Parse a comma-separated CORS origin list.

    - "*" means allow all origins (OK for local dev; avoid in production).
    - Empty means default to localhost dev origins.
    """

    value = (env_value or "").strip()
    if value == "*":
        return ["*"]
    if not value:
        return [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    return [o.strip() for o in value.split(",") if o.strip()]


def create_app() -> FastAPI:
    """Create the FastAPI app.

    Keeping this in a factory makes it easy to test and to run under gunicorn.
    """

    app = FastAPI(title="contoso-admin-orchestrator", version="0.1")
    service = AdminOrchestratorService()

    cors_origins = _parse_cors_origins(os.getenv("ADMIN_ORCH_CORS_ORIGINS", ""))
    if cors_origins == ["*"]:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        """Health probe for App Service and local dev."""

        return {"status": "ok"}

    # NOTE: This endpoint is intentionally synchronous.
    # The orchestrator currently calls MCP tools via `asyncio.run(...)`.
    # FastAPI will run sync endpoints in a threadpool, avoiding nested event-loop
    # errors.
    @app.post("/chat")
    def chat(message: str = Body(..., embed=True)) -> dict[str, str]:
        """Handle one admin chat turn (stateless).

        Request body shape:
            { "message": "..." }

        Response shape:
            { "response": "..." }
        """

        response = service.handle_message(message)
        return {"response": response}

    return app


# ASGI entrypoint for uvicorn/gunicorn.
app = create_app()
