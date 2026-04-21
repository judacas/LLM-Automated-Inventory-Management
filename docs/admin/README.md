# Admin Documentation

[Back to docs index](../README.md)

This folder contains documentation for the **admin-facing** portion of the Contoso system:

- Admin Orchestrator service (HTTP API)
- Local end-to-end validation against Inventory MCP
- Foundry prompt-agent instruction text (routing/intent)

## Quick start (local)

1. Start Inventory MCP

   - See [../inventory/run_inventory_mcp.md](../inventory/run_inventory_mcp.md)

2. Start Admin Orchestrator

   - See [run_admin_orchestrator.md](run_admin_orchestrator.md)

3. Run end-to-end local test (orchestrator → Inventory MCP over HTTP)

   - See [local_e2e_admin_orchestrator_inventory_mcp.md](local_e2e_admin_orchestrator_inventory_mcp.md)

## Foundry prompt agent

- See [foundry_prompt_agent_instructions.md](foundry_prompt_agent_instructions.md)
