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


def _env_truthy(name: str) -> bool:
    """Return True if an env var is set to a truthy value.

    Accepted truthy values: 1, true, yes, on (case-insensitive).

    This helper keeps configuration parsing consistent across the codebase.
    """

    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def build_inventory_service() -> InventoryService:
    """Construct the inventory service.

    Default behavior:
    - If `AZURE_SQL_CONNECTION_STRING` is set, use the SQL-backed repository.
    - Otherwise fall back to the in-memory repository (local dev/tests).

    Production safety switch:
    - If `INVENTORY_REQUIRE_SQL=1` (or true/yes/on), then *absence* of
      `AZURE_SQL_CONNECTION_STRING` is treated as a configuration error.
      This prevents accidentally deploying the mock backend.
    """

    require_sql = _env_truthy("INVENTORY_REQUIRE_SQL")
    has_sql = bool(os.getenv("AZURE_SQL_CONNECTION_STRING"))

    if require_sql and not has_sql:
        raise RuntimeError(
            "INVENTORY_REQUIRE_SQL is enabled, but AZURE_SQL_CONNECTION_STRING is not set. "
            "Set the connection string (App Service app setting) and restart the app."
        )

    if has_sql:
        repo: InventoryRepository = AzureSqlInventoryRepository.from_env()
    else:
        repo = InventoryRepository()  # existing mock/default
    return InventoryService(repo)


def build_inventory_admin_service() -> InventoryAdminService:
    """Construct the admin-facing inventory service.

    Uses Azure SQL when `AZURE_SQL_CONNECTION_STRING` is set, otherwise a mock
    implementation so local development and unit tests are unblocked.
    """

    require_sql = _env_truthy("INVENTORY_REQUIRE_SQL")
    has_sql = bool(os.getenv("AZURE_SQL_CONNECTION_STRING"))

    if require_sql and not has_sql:
        raise RuntimeError(
            "INVENTORY_REQUIRE_SQL is enabled, but AZURE_SQL_CONNECTION_STRING is not set. "
            "Set the connection string (App Service app setting) and restart the app."
        )

    if has_sql:
        repo: InventoryAdminRepository = AzureSqlInventoryAdminRepository.from_env()
    else:
        repo = MockInventoryAdminRepository()
    return InventoryAdminService(repo)
