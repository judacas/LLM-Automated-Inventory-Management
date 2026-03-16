"""Factory for constructing the inventory service.

This repo supports two backing stores:
- A mock/in-memory repository (default) for local dev and unit tests.
- An Azure SQL-backed repository when `AZURE_SQL_CONNECTION_STRING` is set.

Keeping this wiring in one place makes it easy for:
- the MCP server (`inventory_mcp.server`) and
- the legacy REST API (archived at `legacy/rest_tool_api_app.py`)

to share the same business logic layer (`InventoryService`).
"""

import os

from inventory_service.admin_repository import (
    InventoryAdminRepository,
    MockInventoryAdminRepository,
)
from inventory_service.admin_service import InventoryAdminService
from inventory_service.repository import InventoryRepository
from inventory_service.service import InventoryService
from inventory_service.sql_admin_repository import AzureSqlInventoryAdminRepository
from inventory_service.sql_repository import AzureSqlInventoryRepository


def build_inventory_service() -> InventoryService:
    # The presence of this env var is the "switch" between mock vs real database.
    # This is intentionally simple so demos can run without any DB setup.
    if os.getenv("AZURE_SQL_CONNECTION_STRING"):
        repo: InventoryRepository = AzureSqlInventoryRepository.from_env()
    else:
        repo = InventoryRepository()  # existing mock/default
    return InventoryService(repo)


def build_inventory_admin_service() -> InventoryAdminService:
    """Construct the admin-facing inventory service.

    Uses Azure SQL when `AZURE_SQL_CONNECTION_STRING` is set, otherwise a mock
    implementation so local development and unit tests are unblocked.
    """

    if os.getenv("AZURE_SQL_CONNECTION_STRING"):
        repo: InventoryAdminRepository = AzureSqlInventoryAdminRepository.from_env()
    else:
        repo = MockInventoryAdminRepository()
    return InventoryAdminService(repo)
