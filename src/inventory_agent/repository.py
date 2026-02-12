from datetime import date

from inventory_agent.models import InventoryItem


class InventoryRepository:
    """
    Repository layer: data access.

    For now this is mocked.
    Later we will replace internals with Azure SQL queries.
    """

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
