## Inventory Agent - Tool Contract (v0)
### Tool 1: `inventory.get_availability`
- **Purpose:** Return availability for one or more item (SKU)
- **Input:** `items: [{sku: string, requested_qty?: int}]`
- **Output:** `items: [{sku, name, status, qty_available, available_date?}]`
- **Statuses:**
  - `in_stock`
  - `available_on_date`
  - `out_of_stock_unknown`
- **Errors:**
  - `unknown_sku`
  - `invalid_request`
### Tool 2: `inventory.reserve()` (might remove this one)
- **Purpose:** Reserve/reduce inventory due to a PO
- **Input:** 
  - `po_id: string`
  - `customer_id: string`
  - `items: [{ sku: string, qty: int }]`
- **Output:**
  - `reservation_id: string`
  - `status: success | partial | failed`
  - `items: [{ sku, requested_qty, reserved_qty, reason? }]`
- **Rules:**
  - Never reserve negative stock
  - Must be atomic/transactional once wired to DB
### Tool 3: `inventory.apply_shipment`
- **Purpose:** Update inventory from incoming shipments
- **Input:**
  - `shipment_id: string`
  - `items: [{ sku: string, qty: int, available_date?: string }]`
- **Output:**
  - `status: success`
  - `updated_items: [{sku, new_qty, new_status}]`
### Tool 4: `inventory.snapshot`
- **Purpose:** Admin/system summary for inventory health.
- **Output**:
  - totals by status
  - low-stock list
  - next-restock list

## Admin Orchestrator - Intent Contract (v0)
### Supported Intents:
- `check_inventory`
- `check_quotes` (delegates to Quote Agent)
- `system_summary` (calls both inventory and quote agent)
- `unknown` (ask clarifying question)
### Admin outputs must be tool-backed:
- Any counts / totals / "current state" must come from tools (inventory/quote)