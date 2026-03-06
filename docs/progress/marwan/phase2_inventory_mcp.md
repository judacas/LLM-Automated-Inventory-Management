# Phase 2 – Inventory MCP Server

## Goal

Replace the Inventory HTTPS Tool API as the integration boundary with an MCP server that talks directly to the database through the existing `InventoryService` + SQL repository layer.

This phase is intentionally additive: the legacy FastAPI Tool API remains available while MCP is introduced and validated.

---

## Architecture

MCP (FastMCP, Streamable HTTP) → InventoryService → Repository

Repository selection is environment-driven:
- If `AZURE_SQL_CONNECTION_STRING` is set, `AzureSqlInventoryRepository` is used.
- Otherwise, the mocked `InventoryRepository` is used.

---

## MCP Endpoint

Transport: Streamable HTTP

Default MCP path: `/mcp`

Health endpoint: `GET /health`

---

## Tools (initial)

- `get_inventory(product_id: int)`
- `reserve_inventory(product_id: int, qty: int)`
- `receive_inventory(product_id: int, qty: int)`

---

## Run Locally

### WSL/Linux

```bash
uv sync

# Run the MCP server (HTTP)
PYTHONPATH=src uv run uvicorn inventory_mcp.app:app --reload --host 0.0.0.0 --port 8000
```

### Windows PowerShell

```powershell
uv sync
$env:PYTHONPATH = "src"
uv run uvicorn inventory_mcp.app:app --reload --host 0.0.0.0 --port 8000
```

Verify:
- `http://localhost:8000/health`
- MCP endpoint at `http://localhost:8000/mcp`

---

## Azure Demo Deployment (no containers)

Use a managed hosting option that does not require Docker/Container Apps.

Recommended for a fast demo:
- Azure App Service (Python) with a startup command that runs `uvicorn inventory_mcp.app:app ...`

Environment variables to set in Azure:
- `AZURE_SQL_CONNECTION_STRING=<your connection string>` (optional for demo; required for DB-backed runs)
