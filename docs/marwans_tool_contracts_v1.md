# Tool Contracts (v0)

This document captures the current tool surface and orchestration intent contracts.
These are the source-of-truth interfaces used for integration between agents/tools.

---

## Inventory Tool API (v1)

**Type:** Deterministic HTTPS Tool (FastAPI)  
**Base URL (dev):** `https://contoso-inventory-api-13847.azurewebsites.net`  
**Auth:** `x-api-key: <TOOL_API_KEY>` (required for inventory operations)  
**Health endpoint:** public (no key required)

### Endpoint: `GET /health`
- **Purpose:** Service health check
- **Auth:** none
- **Response:**
```json
{ "status": "ok" }
```

### Endpoint: `GET /inventory/get_item/{sku}`
- **Purpose:** Return availability for a single item by SKU
- **Auth:** required `x-api-key`
- **Path Params:**
  - `sku: string`
- **Response:**
```json
{
  "sku": "ABC123",
  "name": "Test Item",
  "quantity": 10,
  "status": "in_stock",
  "available_date": "2026-01-15"
}
```
- **Statuses (current):**
  - `in_stock`
  - `available_on_date`
  - `out_of_stock_unknown`

### Endpoint: `POST /inventory/reserve/{sku}/{qty}`
- **Purpose:** Reserve/reduce inventory quantity for a SKU
- **Auth:** required `x-api-key`
- **Path Params:**
  - `sku: string`
  - `qty: int` (must be positive; validated in service layer)
- **Response:**
```json
{ "status": "reserved", "sku": "ABC123", "qty": 2 }
```
- **Rules (current):**
  - `qty` must be positive
  - Repository update is currently mocked; will become transactional with SQL

### Endpoint: `POST /inventory/receive/{sku}/{qty}`
- **Purpose:** Increase inventory quantity for a SKU
- **Auth:** required `x-api-key`
- **Path Params:**
  - `sku: string`
  - `qty: int` (must be positive; validated in service layer)
- **Response:**
```json
{ "status": "received", "sku": "ABC123", "qty": 5 }
```

## Admin Orchestrator Intent Contract (v1)
**Purpose:** Classify admin requests and route them to the correct tool/agent.

### Supported intents
- `check_inventory`
- `check_quotes` (delegates to quote agent)
- `system_summary` (calls inventory + quote and combines results)
- `unknown`

### Requirements
- Admin outputs must be tool-backed:
  - Any totals/counts/current-state claims must come from deterministic tool calls
- Quote path is currently under development and owned by Quote Agent developer
- Inventory path currently calls the Inventory Tool Service Layer

---
## Notes / Planned Evolution
- Inventory persistence will move from mock repository → Azure SQL repository (Phase 2)
- MCP will be introduced later as the DB access boundary (team responsibility)
- The inventory tool API should remain stable even as the presistence layer changes
  - Inventory Service might become an MCP in future integrations depending on usefulness