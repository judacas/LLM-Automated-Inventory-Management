# Tool Contracts (v1)

This document captures the current tool surface and orchestration intent contracts.
These are the source-of-truth interfaces used for integration between agents/tools.

---

## Inventory Interfaces (v1)

## Inventory MCP Server (v1)

**Type:** MCP Server (Streamable HTTP)  \
**Purpose:** Integration boundary for inventory operations (calls `InventoryService` + repository layer).  \
**MCP Path:** `/mcp`  \
**Health endpoint:** `GET /health`

### Local (dev)
- Base URL: `http://localhost:<port>`
- MCP endpoint: `http://localhost:<port>/mcp`

### Tools
- `get_inventory(product_id: int)`
- `reserve_inventory(product_id: int, qty: int)`
- `receive_inventory(product_id: int, qty: int)`
- `inventory_admin_summary(low_stock_threshold: int = 5)`
- `inventory_unavailable_requested_items(quote_status: str = "Pending", top_n: int = 20)`
- `get_all_inventory()`

---

## Inventory Tool API (legacy, v1)

**Type:** Deterministic HTTPS Tool (FastAPI)  \
**Base URL (dev):** `https://contoso-inventory-api-13847.azurewebsites.net`  \
**Auth:** `x-api-key: <TOOL_API_KEY>` (required for inventory operations)  \
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
  "available_date": "2026-02-25"
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

---

## Admin (Foundry) Notes

- The Admin experience is implemented as a Foundry prompt agent.
- For tool allowlists and copy/paste prompt instructions, see: `docs/admin/foundry_prompt_agent_instructions.md`.

---

## Notes / Planned Evolution

- Inventory persistence will move from mock repository → Azure SQL repository
- Legacy HTTPS Tool API is retained for backward compatibility; MCP is the intended interface going forward
