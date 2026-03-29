# Run Admin Orchestrator (Admin Chat Service)

This service exposes the **admin orchestrator** over HTTP so an admin UI can send chat messages and receive responses.

## What it is

- ASGI app entrypoint: `admin_orchestrator_agent.app:app`
- Endpoints:
  - `GET /health` → `{ "status": "ok" }`
  - `POST /chat` → `{ "response": "..." }`

Under the hood, the orchestrator routes admin requests to deterministic tool calls:
- **Inventory path** → calls Inventory MCP tools (Streamable HTTP) using `INVENTORY_MCP_URL`
- **Quote path** → currently a stub (intended for A2A integration)

## Environment variables

### Required for real MCP calls

- `INVENTORY_MCP_URL`
  - Default: `http://localhost:8000/mcp`
  - If Inventory MCP is deployed: `https://<app>.azurewebsites.net/mcp`

### Optional (dev/test)

- `INVENTORY_MCP_FALLBACK_IN_PROCESS`
  - Default: `1`
  - When `1`, if the MCP HTTP endpoint is unavailable, the orchestrator will call the same inventory service layer in-process.
  - For integration testing (to ensure the orchestrator is truly using MCP), set this to `0`.

- `ADMIN_ORCH_CORS_ORIGINS`
  - CORS origins allowed to call this service from the browser.
  - `*` allows any origin (OK for local demos; avoid in production).
  - Otherwise use comma-separated origins.
  - Default (if unset): `http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000`

- `QUOTE_AGENT_MODE`
  - Default: `null`
  - Current behavior: returns stub responses for quote-related admin questions.
  - Future behavior: additional modes may be added once quote-agent invocation is standardized.

## Local run (WSL/Linux)

From repo root:

```bash
export PYTHONPATH=src
uv run uvicorn admin_orchestrator_agent.app:app --reload --host 0.0.0.0 --port 8010
```

Test:

```bash
curl -s http://localhost:8010/health
curl -s -X POST http://localhost:8010/chat -H 'Content-Type: application/json' -d '{"message":"System summary"}'
```

## Notes

- The `/chat` endpoint is currently **stateless** (one message in → one response out).
- The endpoint is implemented as a **sync** route (FastAPI runs it in a threadpool) to avoid nested event-loop issues.
