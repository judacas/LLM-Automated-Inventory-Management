from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class InventoryItem:
    sku: str
    name: str
    quantity: int
    available_date: Optional[date]
    status: str  # "in_stock" | "available_on_date" | "out_of_stock_unknown"
