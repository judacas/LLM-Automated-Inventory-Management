# Phase 2 – Inventory MCP Server

## Goal

Replace the Inventory HTTPS Tool API as the integration boundary with an MCP server that talks directly to the database through the existing `InventoryService` + SQL repository layer.

This phase is intentionally additive: the legacy FastAPI Tool API is retained in the repo, but MCP is the intended tool interface going forward.

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

---

## Progress Update (2026-03-06)

Demo readiness improvements:

- Fixed MCP mounting so the MCP endpoint is reachable at `http://localhost:<port>/mcp`.
- Improved the default mock `InventoryRepository` so inventory changes are visible across calls (reserve/receive affect subsequent reads) when `AZURE_SQL_CONNECTION_STRING` is not set.
- Added an optional Python demo client (`scripts/mcp_demo_client.py`) as a fallback when Node tooling is unavailable.

Quick demo steps (MCP Inspector UI):

1) Start server (pick an open port if 8000 is busy):

```bash
uv sync
PYTHONPATH=src uv run uvicorn inventory_mcp.app:app --reload --host 0.0.0.0 --port 8001
```

2) Verify health:
- `http://localhost:8001/health`

3) Start Inspector:

```bash
npx -y @modelcontextprotocol/inspector
```

4) Connect Inspector to:
- `http://localhost:8001/mcp`

5) In Inspector, demonstrate tool calls in sequence:
- `get_inventory` with `product_id=1001` (quantity starts at 10)
- `reserve_inventory` with `qty=3`
- `get_inventory` again (quantity now 7)
- `receive_inventory` with `qty=5`
- `get_inventory` again (quantity now 12)

---

## Progress Update (2026-03-12)

Inspector connectivity + MCP endpoint hardening:

- Added CORS support to the ASGI wrapper so the browser-based MCP Inspector UI can call the MCP endpoint from a different localhost port.
	- Configurable via `MCP_CORS_ORIGINS` (set to `*` for local demos).
- Fixed the MCP HTTP transport mounting behavior:
	- The MCP transport is mounted at `/`.
	- The client-facing MCP endpoint remains `/mcp`.
- Normalized the trailing-slash edge case so both `/mcp` and `/mcp/` are accepted.
	- This prevents `307 -> 404` failures when tools/UI add or remove trailing slashes.
- Updated the local runbook to explain the Inspector “proxy token” (token changes every time Inspector restarts).

---

## Progress Update (2026-03-16)

Finished end-to-end local validation (mock mode + real Azure SQL mode) and extended the MCP surface area to support admin inventory requirements.

MCP tools (inventory + admin inventory):
- Existing inventory tools confirmed working: `get_inventory`, `reserve_inventory`, `receive_inventory`.
- Added admin inventory tools:
	- `inventory_admin_summary(low_stock_threshold=5)` for “general inventory system status”.
	- `inventory_unavailable_requested_items(quote_status="Pending", top_n=20)` for “unavailable items being requested”.

Admin orchestrator integration:
- Added an MCP client wrapper used by the admin orchestrator to call inventory tools over Streamable HTTP.
- Added a safe in-process fallback mode for unit tests/local dev when the MCP endpoint is unavailable.
	- Controlled via `INVENTORY_MCP_FALLBACK_IN_PROCESS` (set to `0` to force real MCP HTTP).
	- Endpoint configured via `INVENTORY_MCP_URL`.

Azure SQL local readiness:
- Verified real Azure SQL responses (real `Products.name` and live inventory quantities) through the MCP endpoint.
- Resolved WSL ODBC driver dependency for `pyodbc` by installing/registering the SQL ODBC driver.

Docs + contracts:
- Added an inventory MCP tool contract doc for teammate integration.
- Added an orchestrator→inventory integration doc describing env vars and call patterns.
