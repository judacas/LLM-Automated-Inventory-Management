# Documentation Index

This `docs/` folder is organized by **area** (admin, inventory, deployment, etc.).
Use this page as the entry point, then jump to the relevant subfolder.

## Start here

### Inventory MCP (local)
- Run Inventory MCP locally: [inventory/run_inventory_mcp.md](inventory/run_inventory_mcp.md)
- Validate Inventory MCP against a real SQL database (WSL): [inventory/real_sql_test.md](inventory/real_sql_test.md)

### Admin Orchestrator (local)
- Admin docs landing page: [admin/README.md](admin/README.md)
- Run the Admin Orchestrator HTTP API: [admin/run_admin_orchestrator.md](admin/run_admin_orchestrator.md)
- Local E2E (Admin Orchestrator → Inventory MCP over HTTP): [admin/local_e2e_admin_orchestrator_inventory_mcp.md](admin/local_e2e_admin_orchestrator_inventory_mcp.md)
- Foundry prompt agent instruction text (routing/intent): [admin/foundry_prompt_agent_instructions.md](admin/foundry_prompt_agent_instructions.md)

## Folder map

- [admin/](admin/)
  - Admin orchestrator service runbooks and local E2E validation.

- [inventory/](inventory/)
  - Inventory MCP runbooks (local + real SQL validation).

- [integration/](integration/)
  - Integration notes and cross-component contracts.

- [contracts/](contracts/)
  - Tool contracts and interface specs.

- [deploy/](deploy/)
  - Deployment notes and reference material.

- [progress/](progress/)
  - Project progress notes and historical milestones.

## Merge-friendly docs conventions

- Prefer **adding** new docs over renaming/moving existing docs.
- Keep links **relative** (so they work in GitHub and VS Code).
- Do not commit secrets (connection strings, API keys). Use environment variables.
