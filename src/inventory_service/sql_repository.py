from __future__ import annotations

import os

try:
    import pyodbc  # type: ignore
except ImportError:  # pragma: no cover
    pyodbc = None  # type: ignore

from inventory_service.models import InventoryItem_v2
from inventory_service.repository import InventoryRepository

_CONNECTION_ENV = "AZURE_SQL_CONNECTION_STRING"


class AzureSqlInventoryRepository(InventoryRepository):
    """
    Azure SQL-backed repository using product_id as the primary identifier.
    """

    def __init__(self, connection_string: str) -> None:
        if not connection_string:
            raise RuntimeError(f"{_CONNECTION_ENV} is not set")
        self._cs = connection_string

    @staticmethod
    def from_env() -> "AzureSqlInventoryRepository":
        cs = os.getenv(_CONNECTION_ENV, "")
        return AzureSqlInventoryRepository(cs)

    def _connect(self) -> pyodbc.Connection:
        if pyodbc is None:  # pragma: no cover
            raise RuntimeError(
                "pyodbc is required to use AzureSqlInventoryRepository. "
                "Install it and ensure an ODBC driver is available."
            )
        return pyodbc.connect(self._cs, autocommit=True)

    # --- New product_id based methods ---

    # InventoryRepository-compatible names used by InventoryService v2

    def get_item_v2(self, product_id: int) -> InventoryItem_v2:
        return self.get_item_by_product_id(product_id)

    def update_quantity_v2(self, product_id: int, delta: int) -> None:
        self.update_quantity_by_product_id(product_id, delta)

    def get_item_by_product_id(self, product_id: int) -> InventoryItem_v2:
        query = """
        SELECT TOP (1)
            p.product_id,
            p.name AS product_name,
            COALESCE(i.quantity_in_stock, 0) AS quantity_in_stock,
            i.next_available_date
        FROM dbo.Products p
        LEFT JOIN dbo.Inventory i
            ON i.product_id = p.product_id
        WHERE p.product_id = ?
        ORDER BY i.inventory_id DESC;
        """

        with self._connect() as conn:
            cur = conn.cursor()
            row = cur.execute(query, product_id).fetchone()

        if row is None:
            raise KeyError(f"Unknown product_id: {product_id}")

        qty = int(row.quantity_in_stock)
        next_date = row.next_available_date

        if qty > 0:
            status = "in_stock"
        elif next_date is not None:
            status = "available_on_date"
        else:
            status = "out_of_stock"

        return InventoryItem_v2(
            product_id=int(row.product_id),
            product_name=str(row.product_name),
            quantity=qty,
            available_date=next_date,
            status=status,
        )

    def update_quantity_by_product_id(self, product_id: int, delta: int) -> None:
        # Ensure product exists (clean error if not)
        exists_q = "SELECT 1 FROM dbo.Products WHERE product_id = ?;"
        with self._connect() as conn:
            cur = conn.cursor()
            if cur.execute(exists_q, product_id).fetchone() is None:
                raise KeyError(f"Unknown product_id: {product_id}")

            # Update most recent inventory row if it exists
            upd_q = """
            UPDATE TOP (1) dbo.Inventory
            SET quantity_in_stock = quantity_in_stock + ?,
                last_updated = GETDATE()
            WHERE product_id = ?;
            """
            cur.execute(upd_q, delta, product_id)

            # If no inventory row exists, insert one
            if cur.rowcount == 0:
                ins_q = """
                INSERT INTO dbo.Inventory (product_id, quantity_in_stock, next_available_date, last_updated)
                VALUES (?, ?, NULL, GETDATE());
                """
                cur.execute(ins_q, product_id, delta)

    # --- Compatibility: keep existing interface methods if your service still uses sku ---
    # If your InventoryRepository requires get_item(sku) / update_quantity(sku, delta),
    # keep the mock repo for v1 and do NOT route v1 to SQL yet.
