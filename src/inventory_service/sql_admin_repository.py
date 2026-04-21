from __future__ import annotations

import os
from typing import TYPE_CHECKING

try:
    import pyodbc
except ImportError:  # pragma: no cover
    pyodbc = None

if TYPE_CHECKING:  # pragma: no cover
    import pyodbc as pyodbc_types

from inventory_service.admin_models import (
    InventoryAdminSummary,
    UnavailableRequestedItem,
)
from inventory_service.admin_repository import InventoryAdminRepository

_CONNECTION_ENV = "AZURE_SQL_CONNECTION_STRING"


class AzureSqlInventoryAdminRepository(InventoryAdminRepository):
    """Azure SQL-backed admin queries for inventory/quotes cross-table views.

    Notes:
    - This repo intentionally reads from Quotes/QuoteItems to answer inventory-related
      admin questions like "what unavailable items are customers requesting?".
    - We treat quote data as input signals; we do NOT attempt to manage quote lifecycle here.
    """

    def __init__(self, connection_string: str) -> None:
        if not connection_string:
            raise RuntimeError(f"{_CONNECTION_ENV} is not set")
        self._cs = connection_string

    @staticmethod
    def from_env() -> "AzureSqlInventoryAdminRepository":
        cs = os.getenv(_CONNECTION_ENV, "")
        return AzureSqlInventoryAdminRepository(cs)

    def _connect(self) -> "pyodbc_types.Connection":
        if pyodbc is None:  # pragma: no cover
            raise RuntimeError(
                "pyodbc is required to use AzureSqlInventoryAdminRepository. "
                "Install it and ensure an ODBC driver is available."
            )
        return pyodbc.connect(self._cs, autocommit=True)

    def get_admin_summary(self, *, low_stock_threshold: int) -> InventoryAdminSummary:
        query = """
        WITH inv AS (
            SELECT
                p.product_id,
                COALESCE(i.quantity_in_stock, 0) AS quantity_in_stock,
                i.last_updated
            FROM dbo.Products p
            LEFT JOIN dbo.Inventory i
                ON i.product_id = p.product_id
        )
        SELECT
            COUNT(*) AS total_products,
            SUM(CASE WHEN quantity_in_stock > 0 THEN 1 ELSE 0 END) AS in_stock_products,
            SUM(CASE WHEN quantity_in_stock = 0 THEN 1 ELSE 0 END) AS out_of_stock_products,
            SUM(CASE WHEN quantity_in_stock > 0 AND quantity_in_stock <= ? THEN 1 ELSE 0 END) AS low_stock_products,
            SUM(quantity_in_stock) AS total_units_in_stock,
            MAX(last_updated) AS most_recent_inventory_update
        FROM inv;
        """

        with self._connect() as conn:
            cur = conn.cursor()
            row = cur.execute(query, low_stock_threshold).fetchone()

        # COALESCE-like protection for NULL sums
        total_products = int(row.total_products or 0)
        in_stock_products = int(row.in_stock_products or 0)
        out_of_stock_products = int(row.out_of_stock_products or 0)
        low_stock_products = int(row.low_stock_products or 0)
        total_units_in_stock = int(row.total_units_in_stock or 0)

        # Keep this field JSON-friendly (string) to avoid timezone parsing issues.
        most_recent = None
        if getattr(row, "most_recent_inventory_update", None) is not None:
            most_recent = str(row.most_recent_inventory_update)

        return InventoryAdminSummary(
            total_products=total_products,
            in_stock_products=in_stock_products,
            out_of_stock_products=out_of_stock_products,
            low_stock_products=low_stock_products,
            total_units_in_stock=total_units_in_stock,
            most_recent_inventory_update=most_recent,
        )

    def list_unavailable_requested_items(
        self,
        *,
        quote_status: str,
        top_n: int,
    ) -> list[UnavailableRequestedItem]:
        # Inventory-relevant signal: items on pending quotes that cannot be fulfilled from stock.
        query = """
        WITH requested AS (
            SELECT
                qi.product_id,
                SUM(qi.quantity) AS requested_qty
            FROM dbo.QuoteItems qi
            INNER JOIN dbo.Quotes q
                ON q.quote_id = qi.quote_id
            WHERE
                q.status = ?
                AND qi.product_id IS NOT NULL
            GROUP BY qi.product_id
        ), inv AS (
            SELECT
                p.product_id,
                p.name AS product_name,
                COALESCE(i.quantity_in_stock, 0) AS in_stock_qty,
                i.next_available_date
            FROM dbo.Products p
            LEFT JOIN dbo.Inventory i
                ON i.product_id = p.product_id
        )
        SELECT TOP (?)
            r.product_id,
            inv.product_name,
            r.requested_qty,
            inv.in_stock_qty,
            CASE
                WHEN r.requested_qty - inv.in_stock_qty > 0 THEN r.requested_qty - inv.in_stock_qty
                ELSE 0
            END AS shortfall_qty,
            inv.next_available_date
        FROM requested r
        INNER JOIN inv
            ON inv.product_id = r.product_id
        WHERE (r.requested_qty - inv.in_stock_qty) > 0
        ORDER BY shortfall_qty DESC, r.requested_qty DESC;
        """

        with self._connect() as conn:
            cur = conn.cursor()
            rows = cur.execute(query, quote_status, top_n).fetchall()

        items: list[UnavailableRequestedItem] = []
        for row in rows:
            items.append(
                UnavailableRequestedItem(
                    product_id=int(row.product_id),
                    product_name=str(row.product_name),
                    requested_qty=int(row.requested_qty),
                    in_stock_qty=int(row.in_stock_qty),
                    shortfall_qty=int(row.shortfall_qty),
                    next_available_date=row.next_available_date,
                )
            )
        return items
