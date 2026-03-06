# Run Inventory MCP (no containers)

This project uses a `src/` layout, meaning Python packages like `inventory_mcp` live under `src/inventory_mcp`.

If you run an ASGI server (e.g., Uvicorn) without installing the project, Python may not be able to import `inventory_mcp`, resulting in:

- `ModuleNotFoundError: No module named 'inventory_mcp'`

## ASGI entrypoint

The Inventory MCP server is exposed as an ASGI app at:

- `inventory_mcp.app:app`

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

## Notes

- If you installed the project with `uv pip install -e .`, you do *not* need to set `PYTHONPATH`.
- If you are deploying to Azure later, prefer an install-based approach (editable for dev; non-editable wheel/sdist for CI/CD).
