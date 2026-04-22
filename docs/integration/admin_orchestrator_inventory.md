# Admin Orchestrator → Inventory MCP Integration

This document explains how the admin orchestrator agent should call the inventory MCP server.

## Goal

The orchestrator’s job is **routing/decision logic**. It should not query SQL directly.
Instead, it calls MCP tools exposed by the inventory MCP server.

## Implementation location

- MCP client wrapper: `src/admin_orchestrator_agent/inventory_mcp_client.py`
- Orchestrator logic: `src/admin_orchestrator_agent/service.py`

## Configuration

Set the inventory MCP endpoint:

- `INVENTORY_MCP_URL`
  - Default: `http://localhost:8000/mcp`
  - In App Service: set to your deployed URL, e.g. `https://<app>.azurewebsites.net/mcp`

Optional dev/test behavior:

- `INVENTORY_MCP_FALLBACK_IN_PROCESS`
  - Default: `1`
  - When `1`, if the MCP HTTP endpoint is unavailable, the orchestrator calls the same service layer in-process.
  - For integration testing (to ensure MCP is truly being used), set to `0`.

## Tool mapping (what the orchestrator should call)

### Inventory check

- If the admin message includes a numeric `product_id`: call `get_inventory`.
- Otherwise: call `inventory_admin_summary`.

### System summary (inventory contribution)

- Call `inventory_admin_summary`.
- Call `inventory_unavailable_requested_items` (default: Pending quotes).

## Example (local)

1. Start inventory MCP server:

   ```bash
   uv run uvicorn inventory_mcp.app:app --reload --port 8000
   ```

2. Run your orchestrator tests or a small script that calls `AdminOrchestratorService.handle_message()`.

## Notes

- The inventory MCP server supports mock mode when `AZURE_SQL_CONNECTION_STRING` is not set.
- The tool contract (names/args/outputs) is in [inventory_mcp tool contract](../contracts/inventory_mcp_tools_v1.md).
