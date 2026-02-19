from datetime import date

from inventory_service.models import InventoryItem, InventoryItem_v2


class InventoryRepository:
    """
    Repository layer: data access.

    For now this is mocked.
    Later we will replace internals with Azure SQL queries.
    """

    # --- New product_id based methods ---
    def get_item_v2(self, product_id: int) -> InventoryItem_v2:
        return InventoryItem_v2(
            product_id=product_id,
            product_name="Test Item",
            quantity=10,
            available_date=date(2026, 1, 15),
            status="in_stock",
        )

    def update_quantity_v2(self, product_id: int, delta: int) -> None:
        # Placeholder for DB update
        return None

    # --- Legacy SKU-based methods for backward compatibility ---
    def get_item(self, sku: str) -> InventoryItem:
        return InventoryItem(
            sku=sku,
            name="Test Item",
            quantity=10,
            available_date=date(2026, 1, 15),
            status="in_stock",
        )

    def update_quantity(self, sku: str, delta: int) -> None:
        # Placeholder for DB update
        return None
