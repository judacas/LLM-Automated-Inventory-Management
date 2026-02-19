import os

from inventory_service.repository import InventoryRepository
from inventory_service.service import InventoryService
from inventory_service.sql_repository import AzureSqlInventoryRepository


def build_inventory_service() -> InventoryService:
    if os.getenv("AZURE_SQL_CONNECTION_STRING"):
        repo: InventoryRepository = AzureSqlInventoryRepository.from_env()
    else:
        repo = InventoryRepository()  # existing mock/default
    return InventoryService(repo)
