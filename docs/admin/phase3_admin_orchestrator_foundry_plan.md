# Phase 3: Admin Agent (Foundry + MCP)

[Back to admin docs](README.md)

This guide documents the **Phase 3** target architecture:

- The Admin experience is implemented as a **Foundry prompt agent**.
- The Admin agent calls:
  - **Inventory MCP** (this repo) for inventory-related data
  - **Business MCP** (teammate-owned) for business-wide metrics (users/quotes/dashboard)

This setup is designed to satisfy User Stories #5–#7.

## What changed in this repo (Phase 3)

- Inventory MCP now exposes a tool to list inventory for **all products**: `get_all_inventory`.
- Inventory MCP tool surface now supports admin monitoring queries directly.

## User Stories → Routing Responsibilities

### User Story #5 (Outstanding quotes)

#### Requirements

- Admin can view total number of outstanding quotes.
- Admin can view dollar value of a selected outstanding quote.

#### Routing

- Quote-related questions are answered via **Business MCP** tools (or via your Quote agent if you later add A2A).

### User Story #6 (Requested but unavailable items)

#### Routing

- Inventory-related: route to Inventory MCP tool `inventory_unavailable_requested_items`.

### User Story #7 (General system status)

**Routing**
- Inventory rollups: `inventory_admin_summary`
- Requested-unavailable items: `inventory_unavailable_requested_items`
- Inventory levels for all products: `get_all_inventory`
- Registered users / general metrics: Business MCP (if connected)
- Quote metrics: Business MCP (if connected)

## Foundry prompt instructions

Use the Phase 3 prompt text from:
- [foundry_prompt_agent_instructions.md](foundry_prompt_agent_instructions.md)

That prompt is written for a tool-using admin agent.

## Environment notes

- Inventory MCP is served at `/mcp` (local default: `http://localhost:8000/mcp`).
- Business MCP URL/tool surface is teammate-owned; connect it in Foundry and use an allowlist.
