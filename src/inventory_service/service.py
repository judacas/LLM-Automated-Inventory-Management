from inventory_service.models import InventoryItem
from inventory_service.repository import InventoryRepository


class InventoryService:
    """Business logic layer for inventory operations."""

    def __init__(self, repository: InventoryRepository):
        self.repository = repository

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
