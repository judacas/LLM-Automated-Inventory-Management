from __future__ import annotations

from datetime import date, timedelta

from typing_extensions import TypedDict

from database_tools.database import get_connection


# Typed Contracts
class QuoteItemInput(TypedDict):
    product_id: int
    quantity: int


class ConfirmQuoteRequest(TypedDict):
    domain: str
    items: list[QuoteItemInput]


class FulfillmentItem(TypedDict):
    product_id: int
    name: str
    quantity_requested: int
    quantity_available: int
    next_available_date: str | None
    fulfillment_status: str


class ConfirmQuoteResponse(TypedDict):
    quote_id: int
    status: str
    valid_until: date
    total_amount: float
    fulfillment: list[FulfillmentItem]


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
    line_items: list[QuoteLineItem]


class InventoryItem(TypedDict):
    product_id: int
    name: str
    quantity_in_stock: int


class OutOfStockItem(TypedDict):
    product_id: int
    product_name: str
    quantity_in_stock: int


class QuoteItemByNameInput(TypedDict):
    name: str
    quantity: int


class ConfirmQuoteByNameRequest(TypedDict):
    domain: str
    items: list[QuoteItemByNameInput]


# Quote Agent - User methods
# Helper: Add Business Days
def add_business_days(start: date, days: int) -> date:
    current = start
    added = 0

    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:  # 0–4 are Mon–Fri
            added += 1

    return current


def get_product_id_by_name(name: str) -> int:
    normalized_name = name.strip().lower()

    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT product_id
            FROM Products
            WHERE LOWER(LTRIM(RTRIM(name))) = ?
            """,
            (normalized_name,),
        )

        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"Product '{name}' not found.")

        return int(row.product_id)


def confirm_quote_by_product_name(
    request: ConfirmQuoteByNameRequest,
) -> ConfirmQuoteResponse:
    if not request["items"]:
        raise ValueError("Quote must contain at least one item.")

    resolved_items: list[QuoteItemInput] = []

    for item in request["items"]:
        if item["quantity"] <= 0:
            raise ValueError("Quantity must be greater than zero.")

        product_id = get_product_id_by_name(item["name"])

        resolved_items.append(
            {
                "product_id": product_id,
                "quantity": item["quantity"],
            }
        )

    resolved_request: ConfirmQuoteRequest = {
        "domain": request["domain"],
        "items": resolved_items,
    }

    return confirm_quote(resolved_request)


def confirm_quote(request: ConfirmQuoteRequest) -> ConfirmQuoteResponse:
    """
    Create a quote transactionally.
    Does not reserve or deduct inventory.
    Always accepts quote and provides fulfillment information.
    """

    if not request["items"]:
        raise ValueError("Quote must contain at least one item.")

    for item in request["items"]:
        if item["quantity"] <= 0:
            raise ValueError("Quantity must be greater than zero.")

    normalized_domain = request["domain"].strip().lower()

    with get_connection() as conn:
        conn.autocommit = False
        cursor = conn.cursor()

        try:
            # Resolve account
            cursor.execute(
                """
                SELECT account_id, discount_percent
                FROM BusinessAccounts
                WHERE LOWER(LTRIM(RTRIM(domain))) = ?
                """,
                (normalized_domain,),
            )
            account_row = cursor.fetchone()

            if account_row is None:
                raise ValueError("Business account not found.")

            account_id: int = account_row.account_id
            discount_flag: int = account_row.discount_percent

            # Enforce 5 active quote limit
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

            if count_row[0] >= 5:
                raise ValueError("Maximum of 5 active quotes reached.")

            subtotal = 0.0
            quote_items: list[tuple[int, int, float]] = []
            fulfillment_info: list[FulfillmentItem] = []

            # Retrieve product data (no locking)
            for item in request["items"]:
                cursor.execute(
                    """
                    SELECT p.product_id, p.name, p.price,
                           i.quantity_in_stock, i.next_available_date
                    FROM Products p
                    LEFT JOIN Inventory i
                        ON p.product_id = i.product_id
                    WHERE p.product_id = ?
                    """,
                    (item["product_id"],),
                )

                row = cursor.fetchone()

                if row is None:
                    raise ValueError(f"Product {item['product_id']} not found.")

                quantity_requested = item["quantity"]
                quantity_available = row.quantity_in_stock or 0
                unit_price = float(row.price)

                subtotal += unit_price * quantity_requested
                quote_items.append((row.product_id, quantity_requested, unit_price))

                if quantity_available >= quantity_requested:
                    status = "fully_available"
                elif quantity_available > 0:
                    status = "partially_available"
                else:
                    status = "delayed"

                fulfillment_info.append(
                    {
                        "product_id": row.product_id,
                        "name": row.name,
                        "quantity_requested": quantity_requested,
                        "quantity_available": quantity_available,
                        "next_available_date": (
                            str(row.next_available_date)
                            if row.next_available_date
                            else None
                        ),
                        "fulfillment_status": status,
                    }
                )

            discount_amount = 0.0
            if discount_flag == 1:
                discount_amount = round(subtotal * 0.05, 2)

            total_amount = round(subtotal - discount_amount, 2)
            valid_until = add_business_days(date.today(), 5)

            # Insert Quote
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

            quote_id = int(quote_row[0])

            # Insert QuoteItems (no inventory update)
            for product_id, quantity, unit_price in quote_items:
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
                "fulfillment": fulfillment_info,
            }

        except Exception:
            conn.rollback()
            raise


def expire_quotes() -> None:
    """
    Expires all active quotes past valid_until.
    Runs silently.
    """

    with get_connection() as conn:
        conn.autocommit = False
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE Quotes
                SET status = 'expired'
                WHERE status = 'active'
                AND valid_until < SYSDATETIME()
                """
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def get_active_quotes_by_domain(domain: str) -> list[UserQuoteSummary]:
    normalized_domain = domain.strip().lower()

    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT account_id
            FROM BusinessAccounts
            WHERE LOWER(LTRIM(RTRIM(domain))) = ?
            """,
            (normalized_domain,),
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


# Quote Agent - Admin methods
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

        outstanding_count = int(row[0])
        outstanding_total = float(row[1])

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM Inventory
            WHERE quantity_in_stock = 0
            """
        )
        row2 = cursor.fetchone()
        if row2 is None:
            raise RuntimeError("Failed to fetch out-of-stock count.")

        out_of_stock = int(row2[0])

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
            ORDER BY created_at DESC
            """
        )

        rows = cursor.fetchall()

        return [
            {
                "quote_id": row.quote_id,
                "account_id": row.account_id,
                "status": row.status,
                "created_at": str(row.created_at),
                "valid_until": str(row.valid_until),
                "total_amount": float(row.total_amount),
            }
            for row in rows
        ]


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

        line_items: list[QuoteLineItem] = [
            {
                "product_id": item.product_id,
                "name": item.name,
                "quantity": int(item.quantity),
                "price_at_time": float(item.price_at_time),
                "quantity_in_stock": item.quantity_in_stock,
            }
            for item in items
        ]

        return {
            "quote_id": quote.quote_id,
            "account_id": quote.account_id,
            "status": quote.status,
            "created_at": str(quote.created_at),
            "valid_until": str(quote.valid_until),
            "total_amount": float(quote.total_amount),
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
            ORDER BY p.name
            """
        )

        rows = cursor.fetchall()

        return [
            {
                "product_id": row.product_id,
                "product_name": row.name,
                "quantity_in_stock": int(row.quantity_in_stock),
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
            ORDER BY p.name
            """
        )

        rows = cursor.fetchall()

        return [
            {
                "product_id": row.product_id,
                "name": row.name,
                "quantity_in_stock": int(row.quantity_in_stock),
            }
            for row in rows
        ]


def get_inventory_status_by_name(name: str) -> InventoryStatusResponse:
    normalized_name = name.strip().lower()

    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT p.product_id, p.name, i.quantity_in_stock, i.next_available_date
            FROM Products p
            INNER JOIN Inventory i
                ON p.product_id = i.product_id
            WHERE LOWER(LTRIM(RTRIM(p.name))) = ?
            """,
            (normalized_name,),
        )

        row = cursor.fetchone()
        if row is None:
            raise ValueError("Product not found.")

        quantity = int(row.quantity_in_stock)

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
