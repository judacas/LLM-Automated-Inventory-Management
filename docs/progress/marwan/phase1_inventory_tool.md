# Phase 1 – Inventory Tool API

## Overview

Phase 1 implemented a deterministic inventory service layer and exposed it via a FastAPI tool surface.

That legacy FastAPI API is retained in the repo for reference/backward compatibility, but the current integration boundary (Phase 2) is the Inventory MCP server, which calls the same service layer and talks directly to the configured repository.

---

## Architecture

Legacy: FastAPI → InventoryService → Repository

Current: MCP (FastMCP, Streamable HTTP) → InventoryService → Repository

Current repository is mocked.
Phase 2 will replace it with Azure SQL.

---

## Run Locally

See the current runbook:
- `docs/run_inventory_mcp.md`

## Endpoints
See:
`docs/contracts/marwans_tool_contracts_v1.md`

