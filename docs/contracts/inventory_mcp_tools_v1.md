# Inventory MCP Tool Contract (v1)

This document defines the **inventory** MCP server tool surface so teammates can integrate without reading implementation code.

## Server identity

- **Server name**: `contoso-inventory`
- **Transport**: MCP Streamable HTTP
- **Health**: `GET /health`
- **MCP endpoint**: `/mcp`

## Environment variables

- `AZURE_SQL_CONNECTION_STRING`
  - If set: tools use Azure SQL repositories.
  - If not set: tools fall back to mock/in-memory repositories for local dev/tests.

## Tools

### 1) `get_inventory`
Get inventory status for a product.

**Arguments**
- `product_id` (int, required)

**Structured output**
```json
{
  "product_id": 1001,
  "product_name": "Widget A",
  "quantity": 10,
  "available_date": "2026-04-01",
  "status": "in_stock"
}
```

### 2) `reserve_inventory`
Decreases inventory for a product (side-effect).

**Arguments**
- `product_id` (int, required)
- `qty` (int, required, must be > 0)

**Structured output**
```json
{ "status": "reserved", "product_id": 1001, "qty": 3 }
```

### 3) `receive_inventory`
Increases inventory for a product (side-effect).

**Arguments**
- `product_id` (int, required)
- `qty` (int, required, must be > 0)

**Structured output**
```json
{ "status": "received", "product_id": 1001, "qty": 3 }
```

### 4) `inventory_admin_summary`
Admin-facing inventory rollup metrics.

Supports the requirement: “All general information about the current state of the system / inventory”.

**Arguments**
- `low_stock_threshold` (int, optional, default: 5)

**Structured output**
```json
{
  "total_products": 123,
  "in_stock_products": 100,
  "out_of_stock_products": 23,
  "low_stock_products": 12,
  "total_units_in_stock": 4567,
  "most_recent_inventory_update": "2026-03-16 22:41:09.123"
}
```

### 5) `inventory_unavailable_requested_items`
Returns products that customers are requesting (via quotes) that cannot currently be fulfilled from stock.

Supports the requirement: “What currently unavailable items are being requested by customers”.

**Arguments**
- `quote_status` (str, optional, default: `"Pending"`)
- `top_n` (int, optional, default: 20)

**Structured output**
```json
{
  "quote_status": "Pending",
  "items": [
    {
      "product_id": 1001,
      "product_name": "Widget A",
      "requested_qty": 10,
      "in_stock_qty": 0,
      "shortfall_qty": 10,
      "next_available_date": "2026-04-01"
    }
  ]
}
```

## Error behavior (integration expectations)

- Invalid numeric inputs (e.g., `qty <= 0`) raise tool errors.
- Unknown `product_id` raises a tool error (maps to `KeyError` in service/repo).
- If SQL is enabled but DB connectivity fails, tools raise errors; clients should surface a clear message and/or retry.
