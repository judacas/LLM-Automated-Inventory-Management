"""Inventory domain service (business logic).

This layer is intentionally small and deterministic:
- It performs input validation.
- It delegates persistence to an `InventoryRepository` implementation.

The repository implementation is chosen by `inventory_service.factory`:
- Default: in-memory mock repository (fast local dev + tests)
- When `AZURE_SQL_CONNECTION_STRING` is set: Azure SQL repositories

This service supports two APIs:
- v2 (preferred): product_id-based methods used by the MCP server.
- v1 (legacy): sku-based methods kept for backward compatibility.
"""

from inventory_service.models import InventoryItem, InventoryItem_v2
from inventory_service.repository import InventoryRepository


class InventoryService:
    """Business logic layer for inventory operations."""

    def __init__(self, repository: InventoryRepository):
        self.repository = repository

    # SQL Methods
    def get_inventory_by_product_id(self, product_id: int) -> InventoryItem_v2:
        if product_id <= 0:
            raise ValueError("product_id must be positive.")
        return self.repository.get_item_v2(product_id)

    def reserve_by_product_id(self, product_id: int, quantity: int) -> None:
        if product_id <= 0:
            raise ValueError("product_id must be positive.")
        if quantity <= 0:
            raise ValueError("Quantity must be positive.")
        self.repository.update_quantity_v2(product_id, -quantity)

    def receive_shipment_by_product_id(self, product_id: int, quantity: int) -> None:
        if product_id <= 0:
            raise ValueError("product_id must be positive.")
        if quantity <= 0:
            raise ValueError("Quantity must be positive.")
        self.repository.update_quantity_v2(product_id, quantity)

    # Legacy SKU-based methods for backward compatibility

    def get_item_availability(self, sku: str) -> InventoryItem:
        return self.repository.get_item(sku)

    def reserve_item(self, sku: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("Quantity must be positive.")
        self.repository.update_quantity(sku, -quantity)

    def receive_shipment(self, sku: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("Shipment quantity must be positive.")
        self.repository.update_quantity(sku, quantity)
