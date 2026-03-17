# Run Inventory MCP

This project uses a `src/` layout, meaning Python packages like `inventory_mcp` live under `src/inventory_mcp`.

If you run an ASGI server (e.g., Uvicorn) without installing the project, Python may not be able to import `inventory_mcp`, resulting in:

- `ModuleNotFoundError: No module named 'inventory_mcp'`

## ASGI entrypoint

The Inventory MCP server is exposed as an ASGI app at:

- `inventory_mcp.app:app`

The HTTP endpoints exposed by that app:

- Health probe: `GET /health`
- MCP (Streamable HTTP): `/mcp`

Implementation detail (helpful for debugging):
- The ASGI wrapper mounts the MCP transport at `/` and the transport itself exposes `/mcp`.

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
## Final pre-deploy smoke test (recommended)

Use this checklist the last time you test locally before publishing to Azure.

### 1) Start the ASGI server

Use one of the run commands above (WSL/Linux or PowerShell).

Keep that terminal running.

### 2) Sanity check the two “must work” routes

- Health probe:

```bash
curl -i http://localhost:8000/health
```

- MCP endpoint reachability (both forms):

```bash
curl -i http://localhost:8000/mcp
curl -i http://localhost:8000/mcp/
```

Notes:
- MCP traffic is typically `POST`-driven; `GET` may return a non-200.
- The important part is: it should **not** be a `404` from your app.

### 3) Run the demo client (no Node required)

In a second terminal:

```bash
uv run python scripts/mcp_demo_client.py --url http://localhost:8000/mcp --product-id 1001 --qty 3
```

Expected:
- Prints the tool list (includes `get_inventory`, `reserve_inventory`, `receive_inventory`)
- `reserve_inventory` decreases quantity
- `receive_inventory` increases quantity

### 4) Run unit tests (fast safety check)

From the repo root (new terminal or after stopping Uvicorn):

```bash
uv run pytest
```

### 5) (Optional) Exercise the “real SQL” code path

The MCP server switches repositories based on env var:
- If `AZURE_SQL_CONNECTION_STRING` is set, calls go to Azure SQL repositories.
- If not set, calls use mock/in-memory repositories.

If you have a dev database ready and want to validate the SQL path:

1) Set `AZURE_SQL_CONNECTION_STRING` for your shell session
2) Restart the ASGI server
3) Re-run the demo client

If the DB schema is missing rows (e.g., the `Products` table doesn’t contain your `product_id`), `get_inventory` will fail with a clear `KeyError` surfaced as a tool error.

## Optional: run through Azure Functions locally (deployment-faithful)

If your goal is to validate the *exact hosting model* you will deploy (Functions HTTP trigger + ASGI middleware), do this once before publishing.

### 1) Start Functions host

From the repo root:

```bash
func host start
```

### 2) Verify endpoints

In another terminal:

```bash
curl -i http://localhost:7071/health
curl -i http://localhost:7071/mcp
curl -i http://localhost:7071/mcp/
```

### 3) Run the Python demo client against the Functions host

```bash
uv run python scripts/mcp_demo_client.py --url http://localhost:7071/mcp --product-id 1001 --qty 3
```

If this passes, you’ve validated:
- route forwarding (`InventoryMcpProxy` catch-all)
- host.json routePrefix behavior (no `/api` prefix)
- ASGI adapter behavior (the common source of "works locally, fails in Functions" issues)


## Verify MCP tools (recommended for demos)

The quickest way to *show the tools working* (list tools + invoke them) is the MCP Inspector UI.

1) Start the server (instructions above)
2) In a second terminal, run:

```bash
npx -y @modelcontextprotocol/inspector
```

### Inspector “proxy token” (common connection error)

When the Inspector starts, it prints a **proxy token** in the terminal.

The browser UI uses that token to authenticate to the Inspector’s local proxy.
If you restart the Inspector, the token changes.

If you see an error like:

> Connection Error - Check if your MCP server is running and proxy token is correct

Do this:

1) Make sure the `npx @modelcontextprotocol/inspector` terminal is still running.
2) Copy the **latest** proxy token from that terminal output.
3) Paste it into the Inspector UI’s “Proxy token” field.
4) Try connecting again.

If you had the Inspector UI open from a previous run, refresh the page and paste the new token.

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
