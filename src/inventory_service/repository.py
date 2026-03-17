"""Inventory repository layer (data access).

The MCP server and any other adapters (Azure Functions, legacy REST) rely on this
module to hide the storage backend.

Implementations:
- `InventoryRepository` here is a simple in-memory default used for tests/demos.
- `AzureSqlInventoryRepository` overrides methods to talk to Azure SQL.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from inventory_service.models import InventoryItem, InventoryItem_v2


class InventoryRepository:
    """Default in-memory repository implementation.

    Notes:
    - This class intentionally behaves like a lightweight mock/stub so local
      development can run without provisioning a database.
    - SQL-backed repositories can subclass and override the v2 methods.
    """

    def _ensure_state(self) -> None:
        """Lazily initialize internal state.

        This avoids requiring subclasses (or test doubles) to call
        `super().__init__()`.
        """

        if not hasattr(self, "_items_v2"):
            self._items_v2: dict[int, InventoryItem_v2] = {}
        if not hasattr(self, "_items"):
            self._items: dict[str, InventoryItem] = {}

    # --- New product_id based methods ---
    def get_item_v2(self, product_id: int) -> InventoryItem_v2:
        """Return inventory for the given product_id (mock implementation)."""

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
        """Apply a quantity delta to product_id inventory (mock implementation)."""

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

    # --- Legacy SKU-based methods for backward compatibility ---
    def get_item(self, sku: str) -> InventoryItem:
        """Return inventory for the given sku (mock implementation)."""

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
        """Apply a quantity delta to sku inventory (mock implementation)."""

        self._ensure_state()
        item = self.get_item(sku)
        item.quantity += delta
        if item.quantity <= 0:
            item.quantity = 0
            item.status = "out_of_stock"
        else:
            item.status = "in_stock"
