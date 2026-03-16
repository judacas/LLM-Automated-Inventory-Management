from __future__ import annotations

from datetime import date
from typing import Protocol

from inventory_service.admin_models import (
    InventoryAdminSummary,
    UnavailableRequestedItem,
)


class InventoryAdminRepository(Protocol):
    """Repository interface for admin-facing inventory queries."""

    def get_admin_summary(
        self, *, low_stock_threshold: int
    ) -> InventoryAdminSummary: ...

    def list_unavailable_requested_items(
        self,
        *,
        quote_status: str,
        top_n: int,
    ) -> list[UnavailableRequestedItem]: ...


class MockInventoryAdminRepository:
    """In-memory stub used for local dev and unit tests."""

    def get_admin_summary(self, *, low_stock_threshold: int) -> InventoryAdminSummary:
        _ = low_stock_threshold
        return InventoryAdminSummary(
            total_products=3,
            in_stock_products=2,
            out_of_stock_products=1,
            low_stock_products=1,
            total_units_in_stock=42,
            most_recent_inventory_update=None,
        )

    def list_unavailable_requested_items(
        self,
        *,
        quote_status: str,
        top_n: int,
    ) -> list[UnavailableRequestedItem]:
        _ = (quote_status, top_n)
        return [
            UnavailableRequestedItem(
                product_id=1001,
                product_name="Widget A",
                requested_qty=10,
                in_stock_qty=0,
                shortfall_qty=10,
                next_available_date=date(2026, 4, 1),
            )
        ]
