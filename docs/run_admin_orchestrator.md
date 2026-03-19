# Run Admin Orchestrator (Admin Chat Service)

This service exposes the **admin orchestrator** over HTTP so your teammate’s admin UI can send chat messages and receive responses.

## What it is

- ASGI app entrypoint: `admin_orchestrator_agent.app:app`
- Endpoints:
  - `GET /health` → `{ "status": "ok" }`
  - `POST /chat` → `{ "response": "..." }`

Under the hood, the orchestrator routes admin requests to deterministic tool calls:
- **Inventory path** → calls Inventory MCP tools (Streamable HTTP) using `INVENTORY_MCP_URL`
- **Quote path** → currently a stub (will be implemented via A2A to the quote agent)

## Environment variables

### Required for real MCP calls

- `INVENTORY_MCP_URL`
  - Default: `http://localhost:8000/mcp`
  - If your Inventory MCP is deployed: `https://<app>.azurewebsites.net/mcp`

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
  - Future behavior: we will add an `a2a` mode once your team standardizes how the quote agent is invoked.

## Local run (PowerShell)

From repo root:

```powershell
# Ensure packages are installed (pick the command your project uses)
# uv sync
# python -m pip install -r requirements.txt

$env:PYTHONPATH = "src"
uv run uvicorn admin_orchestrator_agent.app:app --reload --host 0.0.0.0 --port 8010
```

Test:

```powershell
Invoke-RestMethod http://localhost:8010/health
Invoke-RestMethod -Method Post http://localhost:8010/chat -ContentType application/json -Body '{"message":"System summary"}'
```

## Local run (WSL/Linux)

```bash
# uv sync
PYTHONPATH=src uv run uvicorn admin_orchestrator_agent.app:app --reload --host 0.0.0.0 --port 8010
```

## Notes

- The `/chat` endpoint is currently **stateless** (one message in → one response out). We can add session/threading later if your UI needs it.
- Because the orchestrator currently calls MCP tools via `asyncio.run(...)`, the `/chat` endpoint is implemented as a **sync** route (FastAPI runs it in a threadpool).
