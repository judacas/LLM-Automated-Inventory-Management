"""Admin-facing inventory service.

This module provides higher-level queries used by the admin conversational
interface, such as summary rollups and "what requested items are unavailable".

The data access is delegated to an `InventoryAdminRepository`.
"""

from __future__ import annotations

from inventory_service.admin_models import (
    InventoryAdminSummary,
    UnavailableRequestedItem,
)
from inventory_service.admin_repository import InventoryAdminRepository


class InventoryAdminService:
    """Business logic layer for admin-facing inventory questions."""

    def __init__(self, repository: InventoryAdminRepository):
        self.repository = repository

    def get_summary(self, *, low_stock_threshold: int = 5) -> InventoryAdminSummary:
        if low_stock_threshold <= 0:
            raise ValueError("low_stock_threshold must be positive")
        return self.repository.get_admin_summary(
            low_stock_threshold=low_stock_threshold
        )

    def get_unavailable_requested_items(
        self,
        *,
        quote_status: str = "Pending",
        top_n: int = 20,
    ) -> list[UnavailableRequestedItem]:
        if not quote_status:
            raise ValueError("quote_status must be non-empty")
        if top_n <= 0:
            raise ValueError("top_n must be positive")
        return self.repository.list_unavailable_requested_items(
            quote_status=quote_status,
            top_n=top_n,
        )
