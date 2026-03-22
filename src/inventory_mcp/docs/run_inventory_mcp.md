# Run Inventory MCP

This project uses a `src/` layout, meaning Python packages like `inventory_mcp` live under `src/inventory_mcp`.

## ASGI entrypoint

The Inventory MCP server is exposed as an ASGI app at:

- `inventory_mcp.app:app`

Endpoints:
- Health probe: `GET /health`
- MCP (Streamable HTTP): `/mcp`

## Run in WSL/Linux (recommended)

From the repo root:

### Option A (recommended): run with `PYTHONPATH`

```bash
uv sync
export PYTHONPATH=src
uv run uvicorn inventory_mcp.app:app --reload --host 0.0.0.0 --port 8000
```

## Verify it’s up

```bash
curl -s http://localhost:8000/health
```

Expected:

```json
{"status":"ok"}
```

## Exercise MCP tools (no Node required)

With the server running, in a second terminal:

```bash
uv run python scripts/mcp_demo_client.py --url http://localhost:8000/mcp --product-id 1001 --qty 3
```

## Exercise the real SQL code path

See [real_sql_test.md](real_sql_test.md).
