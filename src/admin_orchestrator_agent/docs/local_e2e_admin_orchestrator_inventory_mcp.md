# Local E2E Test: Admin Orchestrator → Inventory MCP (HTTP)

This guide verifies the **option (1)** architecture:

- A chat client calls the **Admin Orchestrator** over HTTP (`POST /chat`)
- The orchestrator calls the **Inventory MCP** over Streamable HTTP (`/mcp`)
- The response is tool-backed (no in-process fallback)

## Prerequisites

- You are using WSL.
- You have `uv` installed and your environment synced.

## Step 0 — Install deps (once per environment)

From repo root:

```bash
uv sync
```

## Step 1 — Start Inventory MCP (terminal 1)

From repo root:

```bash
export PYTHONPATH=src
uv run uvicorn inventory_mcp.app:app --reload --host 0.0.0.0 --port 8000
```

Verify:

```bash
curl -s http://localhost:8000/health
```

Expected:

```json
{"status":"ok"}
```

## Step 2 — Start Admin Orchestrator (terminal 2)

From repo root:

```bash
export PYTHONPATH=src
export INVENTORY_MCP_URL=http://localhost:8000/mcp
export INVENTORY_MCP_FALLBACK_IN_PROCESS=0
uv run uvicorn admin_orchestrator_agent.app:app --reload --host 0.0.0.0 --port 8010
```

Key setting:

- `INVENTORY_MCP_FALLBACK_IN_PROCESS=0` forces a failure if MCP is not reachable.

## Step 3 — Call the orchestrator (terminal 3)

Inventory summary:

```bash
curl -s -X POST http://localhost:8010/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"system summary"}'
```

Inventory check (with product id):

```bash
curl -s -X POST http://localhost:8010/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Check inventory for product 1001"}'
```

## Step 4 — Run automated tests (recommended before commits)

```bash
uv run pytest -k admin_orchestrator
```
