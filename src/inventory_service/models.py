from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class InventoryItem_v2:
    product_id: int
    product_name: str
    quantity: int
    available_date: Optional[date]
    status: str  # "in_stock" | "available_on_date" | "out_of_stock"


@dataclass
class InventoryItem:
    sku: str
    name: str
    quantity: int
    available_date: Optional[date]
    status: str  # "in_stock" | "available_on_date" | "out_of_stock_unknown"
