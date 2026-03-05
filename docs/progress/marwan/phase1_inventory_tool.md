# Phase 1 – Inventory Tool API

## Overview

Phase 1 implements a deterministic inventory service layer and exposes it via a FastAPI tool surface.

This tool will be called by the Admin Orchestrator agent and later integrated with Azure SQL and MCP.

---

## Architecture

FastAPI → InventoryService → Repository

Current repository is mocked.
Phase 2 will replace it with Azure SQL.

---

## Run Locally

```bash
uv sync
export TOOL_API_KEY="dev-key"
PYTHONPATH=src uv run uvicorn tool_api.app:app --reload
```
**API Key is found in the Azure Portal under:** contoso-inventory-api-13847 → Settings (left bar) → Environment Variables

## Endpoints
See:
`docs/contracts/marwans_tool_contracts_v1.md`

