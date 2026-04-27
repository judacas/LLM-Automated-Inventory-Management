from __future__ import annotations

from datetime import date, timedelta
from typing import TypedDict

from mcp.database import get_connection

# -------------------------
# Typed Contracts
# -------------------------


class QuoteItemInput(TypedDict):
    product_id: int
    quantity: int


class PreviewQuoteRequest(TypedDict):
    domain: str
    items: list[QuoteItemInput]


class AvailableItem(TypedDict):
    product_id: int
    name: str
    quantity_requested: int
    quantity_available: int
    unit_price: float
    line_total: float


class UnavailableItem(TypedDict):
    product_id: int
    name: str
    reason: str


class PreviewQuoteResponse(TypedDict):
    can_create_quote: bool
    available_items: list[AvailableItem]
    unavailable_items: list[UnavailableItem]
    missing_products: list[int]
    preview_total: float


class ConfirmQuoteRequest(TypedDict):
    domain: str
    items: list[QuoteItemInput]


class ConfirmQuoteResponse(TypedDict):
    quote_id: int
    status: str
    valid_until: date
    total_amount: float


class UserQuoteSummary(TypedDict):
    quote_id: int
    created_at: str
    valid_until: str
    total_amount: float


class InventoryStatusResponse(TypedDict):
    product_id: int
    name: str
    quantity_in_stock: int
    status: str


class DashboardMetricsResponse(TypedDict):
    outstanding_quotes_count: int
    outstanding_total_amount: float
    out_of_stock_count: int


class QuoteSummary(TypedDict):
    quote_id: int
    account_id: int
    status: str
    created_at: str
    valid_until: str
    total_amount: float
    has_unavailable_items: bool
    unavailable_items_count: int


class QuoteLineItem(TypedDict):
    product_id: int | None
    name: str | None
    quantity: int
    price_at_time: float
    quantity_in_stock: int | None


class QuoteDetailResponse(TypedDict):
    quote_id: int
    account_id: int
    status: str
    created_at: str
    valid_until: str
    total_amount: float
    has_unavailable_items: bool
    unavailable_items_count: int
    line_items: list[QuoteLineItem]


class InventoryItem(TypedDict):
    product_id: int
    name: str
    quantity_in_stock: int


class OutOfStockItem(TypedDict):
    product_id: int
    product_name: str
    quantity_in_stock: int


# -------------------------
# Helper: Add Business Days
# -------------------------


def add_business_days(start: date, days: int) -> date:
    current = start
    added = 0

    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:  # 0–4 are Mon–Fri
            added += 1

    return current


# -------------------------
# Preview Quote
# -------------------------


def preview_quote(request: PreviewQuoteRequest) -> PreviewQuoteResponse:
    """
    Preview a quote without mutating the database.
    Validates products and inventory availability.
    """

    if not request["items"]:
        raise ValueError("Quote must contain at least one item.")

    for item in request["items"]:
        if item["quantity"] <= 0:
            raise ValueError("Quantity must be greater than zero.")

    domain = request["domain"]

    with get_connection() as conn:
        cursor = conn.cursor()

        # Resolve account
        account_query = """
            SELECT account_id, discount_percent
            FROM BusinessAccounts
            WHERE domain = ?
        """

        cursor.execute(account_query, (domain,))
        account_row = cursor.fetchone()

        if account_row is None:
            raise ValueError("Business account not found.")

        discount_flag: int = account_row.discount_percent

        available_items: list[AvailableItem] = []
        unavailable_items: list[UnavailableItem] = []
        missing_products: list[int] = []

        preview_total = 0.0

        for item in request["items"]:
            product_query = """
                SELECT p.product_id, p.name, p.price,
                       i.quantity_in_stock
                FROM Products p
                LEFT JOIN Inventory i
                    ON p.product_id = i.product_id
                WHERE p.product_id = ?
            """

            cursor.execute(product_query, (item["product_id"],))
            row = cursor.fetchone()

            if row is None:
                missing_products.append(item["product_id"])
                continue

            quantity_requested = item["quantity"]
            quantity_available = row.quantity_in_stock or 0

            if quantity_available < quantity_requested:
                unavailable_items.append(
                    {
                        "product_id": row.product_id,
                        "name": row.name,
                        "reason": "insufficient_stock",
                    }
                )
                continue

            unit_price = float(row.price)
            line_total = unit_price * quantity_requested

            preview_total += line_total

            available_items.append(
                {
                    "product_id": row.product_id,
                    "name": row.name,
                    "quantity_requested": quantity_requested,
                    "quantity_available": quantity_available,
                    "unit_price": unit_price,
                    "line_total": line_total,
                }
            )

        # Apply discount at total level
        if discount_flag == 1:
            preview_total *= 0.9  # 10% discount — must match confirm_quote

        return {
            "can_create_quote": len(available_items) > 0,
            "available_items": available_items,
            "unavailable_items": unavailable_items,
            "missing_products": missing_products,
            "preview_total": round(preview_total, 2),
        }


def confirm_quote(request: ConfirmQuoteRequest) -> ConfirmQuoteResponse:
    """
    Confirm and create a quote transactionally.
    Deducts inventory and inserts quote + line items.
    """

    if not request["items"]:
        raise ValueError("Quote must contain at least one item.")

    for item in request["items"]:
        if item["quantity"] <= 0:
            raise ValueError("Quantity must be greater than zero.")

    domain = request["domain"]

    with get_connection() as conn:
        conn.autocommit = False
        cursor = conn.cursor()

        try:
            # -------------------------
            # Resolve account
            # -------------------------
            cursor.execute(
                """
                SELECT account_id, discount_percent
                FROM BusinessAccounts
                WHERE domain = ?
                """,
                (domain,),
            )
            account_row = cursor.fetchone()

            if account_row is None:
                raise ValueError("Business account not found.")

            account_id: int = account_row.account_id
            discount_flag: int = account_row.discount_percent

            # -------------------------
            # Enforce 5 active quote limit
            # -------------------------
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM Quotes
                WHERE account_id = ?
                AND status = 'active'
                """,
                (account_id,),
            )
            count_row = cursor.fetchone()
            if count_row is None:
                raise RuntimeError("Failed to retrieve active quote count.")

            active_count = count_row[0]

            if active_count >= 5:
                raise ValueError("Maximum of 5 active quotes reached.")

            subtotal = 0.0
            validated_items: list[tuple[int, int, float]] = []

            # -------------------------
            # Validate & lock inventory
            # -------------------------
            for item in request["items"]:
                cursor.execute(
                    """
                    SELECT p.price, i.quantity_in_stock
                    FROM Products p
                    INNER JOIN Inventory i WITH (UPDLOCK, ROWLOCK)
                        ON p.product_id = i.product_id
                    WHERE p.product_id = ?
                    """,
                    (item["product_id"],),
                )
                row = cursor.fetchone()

                if row is None:
                    raise ValueError(f"Product {item['product_id']} not found.")

                quantity_available = row.quantity_in_stock
                quantity_requested = item["quantity"]

                if quantity_available < quantity_requested:
                    raise ValueError(
                        f"Insufficient stock for product {item['product_id']}."
                    )

                unit_price = float(row.price)
                subtotal += unit_price * quantity_requested

                validated_items.append(
                    (item["product_id"], quantity_requested, unit_price)
                )

            # -------------------------
            # Apply discount
            # -------------------------
            discount_amount = 0.0
            if discount_flag == 1:
                discount_amount = round(
                    subtotal * 0.10, 2
                )  # 10% — must match preview_quote

            total_amount = round(subtotal - discount_amount, 2)

            # -------------------------
            # Insert Quote
            # -------------------------
            valid_until = add_business_days(date.today(), 5)

            cursor.execute(
                """
                INSERT INTO Quotes (
                    account_id,
                    created_at,
                    valid_until,
                    status,
                    total_amount
                )
                OUTPUT INSERTED.quote_id
                VALUES (?, SYSDATETIME(), ?, 'active', ?)
                """,
                (account_id, valid_until, total_amount),
            )

            quote_row = cursor.fetchone()
            if quote_row is None:
                raise RuntimeError("Failed to retrieve inserted quote ID.")

            quote_id = quote_row[0]

            # -------------------------
            # Insert QuoteItems + Deduct Inventory
            # -------------------------
            for product_id, quantity, unit_price in validated_items:
                cursor.execute(
                    """
                    INSERT INTO QuoteItems (
                        quote_id,
                        product_id,
                        quantity,
                        price_at_time
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (quote_id, product_id, quantity, unit_price),
                )

                cursor.execute(
                    """
                    UPDATE Inventory
                    SET quantity_in_stock = quantity_in_stock - ?,
                        last_updated = SYSDATETIME()
                    WHERE product_id = ?
                    """,
                    (quantity, product_id),
                )

            # -------------------------
            # Insert Discount Line
            # -------------------------
            if discount_amount > 0:
                cursor.execute(
                    """
                    INSERT INTO QuoteItems (
                        quote_id,
                        product_id,
                        quantity,
                        price_at_time
                    )
                    VALUES (?, NULL, 1, ?)
                    """,
                    (quote_id, -discount_amount),
                )

            conn.commit()

            return {
                "quote_id": quote_id,
                "status": "active",
                "valid_until": valid_until,
                "total_amount": total_amount,
            }

        except Exception:
            conn.rollback()
            raise


def expire_quotes() -> None:
    """
    Expires all active quotes past valid_until.
    Restores inventory for expired quotes.
    Runs silently.
    """

    # today = date.today()

    with get_connection() as conn:
        conn.autocommit = False
        cursor = conn.cursor()

        # Find expired active quotes
        cursor.execute(
            """
            SELECT quote_id
            FROM Quotes
            WHERE status = 'active'
            AND valid_until < SYSDATETIME()
            """
        )

        expired_rows = cursor.fetchall()

        for row in expired_rows:
            quote_id = row.quote_id

            try:
                # Get product line items only
                cursor.execute(
                    """
                    SELECT product_id, quantity
                    FROM QuoteItems
                    WHERE quote_id = ?
                    AND product_id IS NOT NULL
                    """,
                    (quote_id,),
                )

                items = cursor.fetchall()

                # Restore inventory
                for item in items:
                    cursor.execute(
                        """
                        UPDATE Inventory
                        SET quantity_in_stock = quantity_in_stock + ?,
                            last_updated = SYSDATETIME()
                        WHERE product_id = ?
                        """,
                        (item.quantity, item.product_id),
                    )

                # Update quote status
                cursor.execute(
                    """
                    UPDATE Quotes
                    SET status = 'expired'
                    WHERE quote_id = ?
                    """,
                    (quote_id,),
                )

                conn.commit()

            except Exception:
                conn.rollback()
                raise


def get_dashboard_metrics() -> DashboardMetricsResponse:
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(total_amount), 0)
            FROM Quotes
            WHERE status = 'active'
            """
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Failed to fetch dashboard metrics.")

        outstanding_count = row[0]
        outstanding_total = float(row[1])

        # Count DISTINCT products customers requested in active quotes
        # that are currently out of stock (matches requirement:
        # "items requested by customers that are currently unavailable")
        cursor.execute(
            """
            SELECT COUNT(DISTINCT qi.product_id)
            FROM QuoteItems qi
            JOIN Inventory i ON qi.product_id = i.product_id
            JOIN Quotes q    ON qi.quote_id    = q.quote_id
            WHERE i.quantity_in_stock = 0
              AND q.status = 'active'
            """
        )
        row2 = cursor.fetchone()
        if row2 is None:
            raise RuntimeError("Failed to fetch out-of-stock count.")

        out_of_stock = row2[0]

        return {
            "outstanding_quotes_count": outstanding_count,
            "outstanding_total_amount": outstanding_total,
            "out_of_stock_count": out_of_stock,
        }


def get_outstanding_quotes() -> list[QuoteSummary]:
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT quote_id, account_id, status, created_at, valid_until, total_amount
            FROM Quotes
            WHERE status = 'active'
            """
        )

        rows = cursor.fetchall()
        results: list[QuoteSummary] = []

        for row in rows:
            results.append(
                {
                    "quote_id": row.quote_id,
                    "account_id": row.account_id,
                    "status": row.status,
                    "created_at": str(row.created_at),
                    "valid_until": str(row.valid_until),
                    "total_amount": float(row.total_amount),
                    "has_unavailable_items": False,
                    "unavailable_items_count": 0,
                }
            )

        return results


def get_quotes_by_email(email: str) -> list[QuoteSummary]:
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT q.quote_id, q.account_id, q.status,
                   q.created_at, q.valid_until, q.total_amount
            FROM Quotes q
            INNER JOIN BusinessAccounts b
                ON q.account_id = b.account_id
            WHERE b.authorized_emails LIKE ?
            """,
            (f"%{email}%",),
        )

        rows = cursor.fetchall()
        results: list[QuoteSummary] = []

        for row in rows:
            results.append(
                {
                    "quote_id": row.quote_id,
                    "account_id": row.account_id,
                    "status": row.status,
                    "created_at": str(row.created_at),
                    "valid_until": str(row.valid_until),
                    "total_amount": float(row.total_amount),
                    "has_unavailable_items": False,
                    "unavailable_items_count": 0,
                }
            )

        return results


def get_quote_by_id(quote_id: int) -> QuoteDetailResponse:
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT quote_id, account_id, status, created_at, valid_until, total_amount
            FROM Quotes
            WHERE quote_id = ?
            """,
            (quote_id,),
        )

        quote = cursor.fetchone()
        if quote is None:
            raise ValueError("Quote not found.")

        cursor.execute(
            """
            SELECT qi.product_id, p.name, qi.quantity,
                   qi.price_at_time, i.quantity_in_stock
            FROM QuoteItems qi
            LEFT JOIN Products p
                ON qi.product_id = p.product_id
            LEFT JOIN Inventory i
                ON qi.product_id = i.product_id
            WHERE qi.quote_id = ?
            """,
            (quote_id,),
        )

        items = cursor.fetchall()
        line_items: list[QuoteLineItem] = []

        for item in items:
            line_items.append(
                {
                    "product_id": item.product_id,
                    "name": item.name,
                    "quantity": item.quantity,
                    "price_at_time": float(item.price_at_time),
                    "quantity_in_stock": item.quantity_in_stock,
                }
            )

        return {
            "quote_id": quote.quote_id,
            "account_id": quote.account_id,
            "status": quote.status,
            "created_at": str(quote.created_at),
            "valid_until": str(quote.valid_until),
            "total_amount": float(quote.total_amount),
            "has_unavailable_items": False,
            "unavailable_items_count": 0,
            "line_items": line_items,
        }


def get_out_of_stock_items() -> list[OutOfStockItem]:
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT p.product_id, p.name, i.quantity_in_stock
            FROM Inventory i
            INNER JOIN Products p
                ON i.product_id = p.product_id
            WHERE i.quantity_in_stock = 0
            """
        )

        rows = cursor.fetchall()

        return [
            {
                "product_id": row.product_id,
                "product_name": row.name,
                "quantity_in_stock": row.quantity_in_stock,
            }
            for row in rows
        ]


def get_all_inventory() -> list[InventoryItem]:
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT p.product_id, p.name, i.quantity_in_stock
            FROM Inventory i
            INNER JOIN Products p
                ON i.product_id = p.product_id
            """
        )

        rows = cursor.fetchall()

        return [
            {
                "product_id": row.product_id,
                "name": row.name,
                "quantity_in_stock": row.quantity_in_stock,
            }
            for row in rows
        ]


def get_active_quotes_by_domain(domain: str) -> list[UserQuoteSummary]:
    with get_connection() as conn:
        cursor = conn.cursor()

        # Resolve account_id
        cursor.execute(
            """
            SELECT account_id
            FROM BusinessAccounts
            WHERE domain = ?
            """,
            (domain,),
        )

        account_row = cursor.fetchone()
        if account_row is None:
            raise ValueError("Business account not found.")

        account_id = account_row.account_id

        cursor.execute(
            """
            SELECT quote_id, created_at, valid_until, total_amount
            FROM Quotes
            WHERE account_id = ?
            AND status = 'active'
            ORDER BY created_at DESC
            """,
            (account_id,),
        )

        rows = cursor.fetchall()

        return [
            {
                "quote_id": row.quote_id,
                "created_at": str(row.created_at),
                "valid_until": str(row.valid_until),
                "total_amount": float(row.total_amount),
            }
            for row in rows
        ]


def get_inventory_status_by_name(name: str) -> InventoryStatusResponse:
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT p.product_id, p.name, i.quantity_in_stock, i.next_available_date
            FROM Products p
            INNER JOIN Inventory i
                ON p.product_id = i.product_id
            WHERE LOWER(p.name) = LOWER(?)
            """,
            (name,),
        )

        row = cursor.fetchone()
        if row is None:
            raise ValueError("Product not found.")

        quantity = row.quantity_in_stock

        if quantity > 0:
            status = "In Stock"
        elif row.next_available_date is not None:
            status = f"Available on {row.next_available_date}"
        else:
            status = "Out of Stock"

        return {
            "product_id": row.product_id,
            "name": row.name,
            "quantity_in_stock": quantity,
            "status": status,
        }
