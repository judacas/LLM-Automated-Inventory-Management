from decimal import Decimal

from typing_extensions import TypedDict

from database_tools.services.quote_service import expire_quotes

from ..database import get_connection


class CreatePurchaseOrderInput(TypedDict):
    quote_id: int
    email: str | None


class PurchaseOrderItemResult(TypedDict):
    product_id: int
    quantity_requested: int
    quantity_fulfilled: int
    quantity_pending: int
    price_at_time: float


class PurchaseOrderResult(TypedDict):
    purchase_order_id: int
    quote_id: int
    account_id: int
    status: str
    total_amount: float
    items: list[PurchaseOrderItemResult]


class PurchaseOrderSummary(TypedDict):
    purchase_order_id: int
    quote_id: int
    status: str
    created_at: str
    total_amount: float


def create_purchase_order(data: CreatePurchaseOrderInput) -> PurchaseOrderResult:
    expire_quotes()

    quote_id = data["quote_id"]
    email = data["email"]
    normalized_email = email.strip().lower() if email is not None else None

    with get_connection() as conn:
        conn.autocommit = False
        cursor = conn.cursor()

        try:
            # Validate Quote Exists
            cursor.execute(
                """
                SELECT quote_id, account_id, status, total_amount
                FROM Quotes
                WHERE quote_id = ?
                """,
                (quote_id,),
            )

            quote_row = cursor.fetchone()

            if quote_row is None:
                raise ValueError("Quote does not exist")

            account_id = quote_row.account_id
            quote_status = quote_row.status
            quote_total_amount: Decimal = quote_row.total_amount

            if quote_status != "active":
                raise ValueError("Quote is not active and cannot be converted")

            # Optional Email Validation
            if normalized_email is not None:
                cursor.execute(
                    """
                    SELECT account_id
                    FROM BusinessAccounts
                    WHERE LOWER(LTRIM(RTRIM(email))) = ?
                    """,
                    (normalized_email,),
                )

                email_row = cursor.fetchone()

                if email_row is None:
                    raise ValueError("Email does not exist")

                if email_row.account_id != account_id:
                    raise ValueError("Quote does not belong to this email")

            # Prevent Duplicate Conversion
            cursor.execute(
                """
                SELECT purchase_order_id
                FROM PurchaseOrders
                WHERE quote_id = ?
                """,
                (quote_id,),
            )

            if cursor.fetchone() is not None:
                raise ValueError("This quote has already been converted")

            # Fetch Quote Items (Exclude Discount Line)
            cursor.execute(
                """
                SELECT product_id, quantity, price_at_time
                FROM QuoteItems
                WHERE quote_id = ?
                AND product_id IS NOT NULL
                """,
                (quote_id,),
            )

            quote_items = cursor.fetchall()

            if not quote_items:
                raise ValueError("Quote contains no items")

            order_items: list[PurchaseOrderItemResult] = []

            total_requested = 0
            total_fulfilled = 0

            # Inventory Processing
            for item in quote_items:
                product_id = item.product_id
                quantity_requested = int(item.quantity)
                price = float(item.price_at_time)

                total_requested += quantity_requested

                # Lock inventory row
                cursor.execute(
                    """
                    SELECT quantity_in_stock
                    FROM Inventory WITH (UPDLOCK, ROWLOCK)
                    WHERE product_id = ?
                    """,
                    (product_id,),
                )

                inventory_row = cursor.fetchone()

                if inventory_row is None:
                    raise ValueError(f"Inventory missing for product {product_id}")

                quantity_available = int(inventory_row.quantity_in_stock)

                quantity_fulfilled = min(quantity_requested, quantity_available)
                quantity_pending = quantity_requested - quantity_fulfilled

                total_fulfilled += quantity_fulfilled

                # Deduct fulfilled quantity
                if quantity_fulfilled > 0:
                    cursor.execute(
                        """
                        UPDATE Inventory
                        SET quantity_in_stock = quantity_in_stock - ?
                        WHERE product_id = ?
                        """,
                        (quantity_fulfilled, product_id),
                    )

                order_items.append(
                    {
                        "product_id": product_id,
                        "quantity_requested": quantity_requested,
                        "quantity_fulfilled": quantity_fulfilled,
                        "quantity_pending": quantity_pending,
                        "price_at_time": price,
                    }
                )

            # Determine Order Status
            if total_fulfilled == total_requested:
                order_status = "fulfilled"
            elif total_fulfilled > 0:
                order_status = "partially_delayed"
            else:
                order_status = "delayed"

            # Insert Purchase Order
            cursor.execute(
                """
                INSERT INTO PurchaseOrders (
                    quote_id,
                    account_id,
                    created_at,
                    status,
                    total_amount
                )
                OUTPUT INSERTED.purchase_order_id
                VALUES (?, ?, SYSDATETIME(), ?, ?)
                """,
                (quote_id, account_id, order_status, quote_total_amount),
            )

            po_row = cursor.fetchone()

            if po_row is None:
                raise RuntimeError("Failed to retrieve purchase_order_id after insert")

            purchase_order_id = int(po_row.purchase_order_id)

            # Insert Purchase Order Items
            for item in order_items:
                cursor.execute(
                    """
                    INSERT INTO PurchaseOrderItems (
                        purchase_order_id,
                        product_id,
                        quantity_requested,
                        quantity_fulfilled,
                        quantity_pending,
                        price_at_time
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        purchase_order_id,
                        item["product_id"],
                        item["quantity_requested"],
                        item["quantity_fulfilled"],
                        item["quantity_pending"],
                        item["price_at_time"],
                    ),
                )

            # Update Quote Status
            cursor.execute(
                """
                UPDATE Quotes
                SET status = 'ordered'
                WHERE quote_id = ?
                """,
                (quote_id,),
            )

            conn.commit()

            return {
                "purchase_order_id": purchase_order_id,
                "quote_id": quote_id,
                "account_id": account_id,
                "status": order_status,
                "total_amount": float(quote_total_amount),
                "items": order_items,
            }

        except Exception:
            conn.rollback()
            raise


def get_purchase_orders_by_email(email: str) -> list[PurchaseOrderSummary]:
    normalized_email = email.strip().lower()

    with get_connection() as conn:
        cursor = conn.cursor()

        # Resolve account
        cursor.execute(
            """
            SELECT account_id
            FROM BusinessAccounts
            WHERE LOWER(LTRIM(RTRIM(email))) = ?
            """,
            (normalized_email,),
        )

        row = cursor.fetchone()
        if row is None:
            raise ValueError("Business account not found.")

        account_id = row.account_id

        cursor.execute(
            """
            SELECT purchase_order_id,
                   quote_id,
                   status,
                   created_at,
                   total_amount
            FROM PurchaseOrders
            WHERE account_id = ?
            ORDER BY created_at DESC
            """,
            (account_id,),
        )

        rows = cursor.fetchall()

        return [
            {
                "purchase_order_id": r.purchase_order_id,
                "quote_id": r.quote_id,
                "status": r.status,
                "created_at": str(r.created_at),
                "total_amount": float(r.total_amount),
            }
            for r in rows
        ]