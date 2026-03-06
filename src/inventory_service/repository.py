from dataclasses import replace
from datetime import date

from inventory_service.models import InventoryItem, InventoryItem_v2


class InventoryRepository:
    """
    Repository layer: data access.

    For now this is mocked.
    Later we will replace internals with Azure SQL queries.
    """

    def _ensure_state(self) -> None:
        # Lazy init to avoid requiring subclasses to call super().__init__().
        if not hasattr(self, "_items_v2"):
            self._items_v2: dict[int, InventoryItem_v2] = {}
        if not hasattr(self, "_items"):
            self._items: dict[str, InventoryItem] = {}

    # --- New product_id based methods ---
    def get_item_v2(self, product_id: int) -> InventoryItem_v2:
        self._ensure_state()
        if product_id not in self._items_v2:
            self._items_v2[product_id] = InventoryItem_v2(
                product_id=product_id,
                product_name="Test Item",
                quantity=10,
                available_date=date(2026, 1, 15),
                status="in_stock",
            )
        return self._items_v2[product_id]

    def update_quantity_v2(self, product_id: int, delta: int) -> None:
        self._ensure_state()
        item = self.get_item_v2(product_id)
        new_quantity = item.quantity + delta
        if new_quantity <= 0:
            new_quantity = 0
            new_status = "out_of_stock"
        else:
            new_status = "in_stock"

        self._items_v2[product_id] = replace(
            item, quantity=new_quantity, status=new_status
        )
        return None

    # --- Legacy SKU-based methods for backward compatibility ---
    def get_item(self, sku: str) -> InventoryItem:
        self._ensure_state()
        if sku not in self._items:
            self._items[sku] = InventoryItem(
                sku=sku,
                name="Test Item",
                quantity=10,
                available_date=date(2026, 1, 15),
                status="in_stock",
            )
        return self._items[sku]

    def update_quantity(self, sku: str, delta: int) -> None:
        self._ensure_state()
        item = self.get_item(sku)
        item.quantity += delta
        if item.quantity <= 0:
            item.quantity = 0
            item.status = "out_of_stock"
        else:
            item.status = "in_stock"
        return None
