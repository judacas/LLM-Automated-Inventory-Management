"""Inventory data models shared across service layers.

These dataclasses are used for:
- internal service/repository return types
- MCP tool output shaping (converted to JSON-serializable dicts)
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class InventoryItem_v2:
    """Product-id based inventory record (preferred)."""

    product_id: int
    product_name: str
    quantity: int
    available_date: Optional[date]
    status: str  # "in_stock" | "available_on_date" | "out_of_stock"


@dataclass
class InventoryItem:
    """SKU-based inventory record (legacy/backward compatibility)."""

    sku: str
    name: str
    quantity: int
    available_date: Optional[date]
    status: str  # "in_stock" | "available_on_date" | "out_of_stock_unknown"
