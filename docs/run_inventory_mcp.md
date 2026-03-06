# Run Inventory MCP (no containers)

This project uses a `src/` layout, meaning Python packages like `inventory_mcp` live under `src/inventory_mcp`.

If you run an ASGI server (e.g., Uvicorn) without installing the project, Python may not be able to import `inventory_mcp`, resulting in:

- `ModuleNotFoundError: No module named 'inventory_mcp'`

## ASGI entrypoint

The Inventory MCP server is exposed as an ASGI app at:

- `inventory_mcp.app:app`

The HTTP endpoints exposed by that app:

- Health probe: `GET /health`
- MCP (Streamable HTTP): `/mcp`

## Run in WSL/Linux (recommended)

From the repo root:

### Option A (recommended): install project in editable mode

This makes the `src/` packages importable everywhere in the venv.

```bash
uv sync
uv pip install -e .
uv run uvicorn inventory_mcp.app:app --reload --host 0.0.0.0 --port 8000
```

### Option B: run without installing (set `PYTHONPATH`)

```bash
uv sync
PYTHONPATH=src uv run uvicorn inventory_mcp.app:app --reload --host 0.0.0.0 --port 8000
```

## Run in Windows PowerShell

From the repo root:

```powershell
uv sync
$env:PYTHONPATH = "src"
uv run uvicorn inventory_mcp.app:app --reload --host 0.0.0.0 --port 8000
```

## Verify it’s up

```bash
curl http://localhost:8000/health
```

PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

You should see:

```json
{"status":"ok"}
```

## Verify MCP tools (recommended for demos)

The quickest way to *show the tools working* (list tools + invoke them) is the MCP Inspector UI.

1) Start the server (instructions above)
2) In a second terminal, run:

```bash
npx -y @modelcontextprotocol/inspector
```

3) In the Inspector UI, connect to:

- `http://localhost:8000/mcp`

If you started Uvicorn on a different port (for example, `8001`), use that instead:

- `http://localhost:8001/mcp`

You should be able to:

- List tools: `get_inventory`, `reserve_inventory`, `receive_inventory`
- Invoke a tool and see structured JSON results

## Verify MCP tools (no Node required)

If `npx` is unavailable (or your Node setup is acting up), you can demo the tools using the included Python client.

With the server running, in a second terminal:

```bash
uv run python scripts/mcp_demo_client.py --url http://localhost:8000/mcp --product-id 1001 --qty 3
```

Expected behavior (using the default mock repository):

- The script lists available tools
- `get_inventory` returns quantity (starts at 10 for a new product_id)
- `reserve_inventory` decreases quantity
- `receive_inventory` increases quantity

## Notes

- If you installed the project with `uv pip install -e .`, you do *not* need to set `PYTHONPATH`.
- If you are deploying to Azure later, prefer an install-based approach (editable for dev; non-editable wheel/sdist for CI/CD).
