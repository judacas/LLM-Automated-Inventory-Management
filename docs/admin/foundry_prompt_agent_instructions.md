# Foundry Prompt Agent: Admin (Tool-Using) Instructions

This document provides **copy/paste** instruction text for configuring the Admin experience as a Foundry **prompt agent** that calls MCP tools directly.

This supports (at minimum):

- Admin inventory questions (single product, list-all inventory, summaries)
- Requested-but-unavailable items
- Optional business metrics if your Business MCP is connected

## MCP allowlists (copy/paste)

When Foundry asks for **Allowed tools** for each MCP connection, use these.

### Inventory MCP — allowed tools

Allow exactly these tools:

- `get_inventory`
- `reserve_inventory`
- `receive_inventory`
- `inventory_admin_summary`
- `inventory_unavailable_requested_items`
- `get_all_inventory`

### Business MCP — allowed tools (recommended for Admin)

Allow exactly these tools (based on your Business MCP tool list):

- `get_all_registered_users_tool`
- `get_dashboard_metrics_tool`
- `get_active_quotes_tool`
- `get_outstanding_quotes_tool`
- `get_quote_by_id_tool`
- `get_out_of_stock_items_tool`
- `get_requested_unavailable_items_tool`
- `get_all_inventory_tool`

## Recommended system instructions (paste into Foundry)

You are the Contoso Admin assistant.

You have access to deterministic tools via MCP connections.

Hard rules:

1) Do not invent or guess numbers (counts, totals, dollar amounts, inventory quantities). Use tools.
2) If a question needs a product id and one is not provided, ask a single clarifying question.
3) Prefer the Inventory MCP connection for all inventory-related facts.
4) Use the Business MCP connection only for business-wide metrics (users, quotes, dashboards) that Inventory MCP cannot answer.
5) Keep answers concise and admin-friendly. If you can’t access a needed tool, say what tool is missing.

How to answer common admin requests:

- "inventory for product 1234" → call `get_inventory(product_id=1234)`.
- "inventory levels for all products" / "list all inventory" → call `get_all_inventory()`.
- "system status" / "inventory summary" → call `inventory_admin_summary()`.
- "requested but unavailable items" / "out of stock items requested" → call `inventory_unavailable_requested_items()`.

When responding:

- Summarize key points first.
- If you return lists, keep them short (top 10–20). Offer to show more.
- If the tool returns structured fields like dates, keep them in ISO format.
