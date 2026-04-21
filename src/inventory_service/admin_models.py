from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class InventoryAdminSummary:
    """High-level inventory metrics used by the admin dashboard/chat."""

    total_products: int
    in_stock_products: int
    out_of_stock_products: int
    low_stock_products: int
    total_units_in_stock: int
    most_recent_inventory_update: Optional[str]


@dataclass(frozen=True)
class UnavailableRequestedItem:
    """A product requested by customers that is not currently fulfillable from stock."""

    product_id: int
    product_name: str
    requested_qty: int
    in_stock_qty: int
    shortfall_qty: int
    next_available_date: Optional[date]
