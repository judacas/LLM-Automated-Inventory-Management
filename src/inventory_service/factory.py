"""Factory for constructing the inventory service.

This repo supports two backing stores:
- A mock/in-memory repository (default) for local dev and unit tests.
- An Azure SQL-backed repository when `AZURE_SQL_CONNECTION_STRING` is set.

Keeping this wiring in one place makes it easy for:
- the MCP server (`inventory_mcp.server`) and
- the legacy REST API (`tool_api.app`)

to share the same business logic layer (`InventoryService`).
"""

import os

from inventory_service.repository import InventoryRepository
from inventory_service.service import InventoryService
from inventory_service.sql_repository import AzureSqlInventoryRepository


def build_inventory_service() -> InventoryService:
    # The presence of this env var is the "switch" between mock vs real database.
    # This is intentionally simple so demos can run without any DB setup.
    if os.getenv("AZURE_SQL_CONNECTION_STRING"):
        repo: InventoryRepository = AzureSqlInventoryRepository.from_env()
    else:
        repo = InventoryRepository()  # existing mock/default
    return InventoryService(repo)
