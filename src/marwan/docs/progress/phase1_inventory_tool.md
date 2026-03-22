# Phase 1 – Inventory Tool API

## Overview

Phase 1 implemented a deterministic inventory service layer and exposed it via a FastAPI tool surface.

That legacy FastAPI API is retained in the repo for reference/backward compatibility, but the current integration boundary (Phase 2) is the Inventory MCP server, which calls the same service layer and talks directly to the configured repository.

---

## Architecture

Legacy: FastAPI → InventoryService → Repository

Current: MCP (FastMCP, Streamable HTTP) → InventoryService → Repository

Repository selection is environment-driven:
- If `AZURE_SQL_CONNECTION_STRING` is set, the SQL-backed repository is used.
- Otherwise, a mock/in-memory repository is used for local dev and unit tests.

---

## Run Locally

See the current runbook:
- [Run Inventory MCP](../../../inventory_mcp/docs/run_inventory_mcp.md)

## Endpoints

See:
- [Tool contracts (v1)](../../../inventory_mcp/docs/contracts/tool_contracts_v1.md)
