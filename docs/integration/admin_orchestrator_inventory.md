# Admin Agent (Foundry) → Inventory MCP Integration

This document explains how a Foundry Admin prompt agent should use the Inventory MCP server.

## Goal

The Admin agent should not query SQL directly.
Instead, it calls deterministic MCP tools exposed by the Inventory MCP server.

## Where the tools live

- Inventory MCP server implementation: `src/inventory_mcp/server.py`
- Inventory MCP tool contract: `docs/contracts/inventory_mcp_tools_v1.md`

## Configuration

Set the inventory MCP endpoint:

- `INVENTORY_MCP_URL`
  - Default: `http://localhost:8000/mcp`
  - In App Service: set to your deployed URL, e.g. `https://<app>.azurewebsites.net/mcp`

## Notes

- For local testing, follow: `docs/inventory/run_inventory_mcp.md`
- For SQL-backed validation, follow: `docs/inventory/real_sql_test.md`

## Tool mapping (what the Admin agent should call)

### Inventory check
- If the admin message includes a numeric `product_id`: call `get_inventory`.
- Otherwise: call `inventory_admin_summary`.

### List all inventory
- If the admin asks to list inventory levels for all products: call `get_all_inventory`.

### System summary (inventory contribution)
- Call `inventory_admin_summary`.
- Call `inventory_unavailable_requested_items` (default: Pending quotes).

The inventory MCP server supports mock mode when `AZURE_SQL_CONNECTION_STRING` is not set.
