from __future__ import annotations

from datetime import date
from typing import TypedDict

from mcp.database import get_connection


class InventoryResponse(TypedDict):
    product_id: int
    name: str
    description: str
    price: float
    quantity_in_stock: int
    availability_status: str
    next_available_date: date | None


def get_inventory_by_product_id(product_id: int) -> InventoryResponse:
    """
    Fetch product and inventory details for a given product ID.
    Applies business rules to compute availability status.
    """

    query = """
        SELECT 
            p.product_id,
            p.name,
            p.description,
            p.price,
            i.quantity_in_stock,
            i.next_available_date
        FROM Products p
        INNER JOIN Inventory i ON p.product_id = i.product_id
        WHERE p.product_id = ?
    """

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (product_id,))
        row = cursor.fetchone()

        if row is None:
            raise ValueError("Product not found")

        quantity: int = row.quantity_in_stock
        next_date: date | None = row.next_available_date

        if quantity > 0:
            availability = "In Stock"
        elif next_date is not None:
            availability = f"Available on {next_date.isoformat()}"
        else:
            availability = "Out of Stock"

        return {
            "product_id": row.product_id,
            "name": row.name,
            "description": row.description,
            "price": float(row.price),
            "quantity_in_stock": quantity,
            "availability_status": availability,
            "next_available_date": next_date,
        }