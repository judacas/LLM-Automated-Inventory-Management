from typing_extensions import TypedDict

from database_tools.database import get_connection


class BusinessAccount(TypedDict):
    account_id: int
    company_name: str
    address: str
    business_type: str
    billing_method: str
    discount_percent: int
    email: str


APPROVED_BILLING_METHODS = {
    "credit card": "credit_card",
    "mailed invoice": "mailed_invoice",
    "mailed invoices": "mailed_invoice",
    "wire transfer": "wire_transfer",
    "ach": "ach",
    "bank transfer": "bank_transfer",
}


def normalize_billing_method(billing_method: str) -> str:
    normalized = billing_method.strip().lower()
    normalized = normalized.replace("_", " ").replace("-", " ")
    normalized = " ".join(normalized.split())

    if not normalized:
        raise ValueError("billing_method is required")

    if normalized not in APPROVED_BILLING_METHODS:
        valid_methods = sorted(set(APPROVED_BILLING_METHODS.values()))
        raise ValueError(
            f"billing_method is invalid. Approved methods: {', '.join(valid_methods)}"
        )

    return APPROVED_BILLING_METHODS[normalized]


def get_business_emails(limit: int = 10) -> list[str]:
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT TOP (?) email
            FROM BusinessAccounts
            WHERE email IS NOT NULL
            ORDER BY account_id
            """,
            (limit,),
        )

        rows = cursor.fetchall()
        return [str(row.email) for row in rows]
    finally:
        conn.close()


def get_business_by_email(email: str) -> BusinessAccount | None:
    conn = get_connection()
    cursor = conn.cursor()

    try:
        normalized_email = email.strip().lower()

        cursor.execute(
            """
            SELECT account_id,
                   company_name,
                   address,
                   business_type,
                   billing_method,
                   discount_percent,
                   email
            FROM BusinessAccounts
            WHERE LOWER(LTRIM(RTRIM(email))) = ?
            """,
            (normalized_email,),
        )

        row = cursor.fetchone()

        if not row:
            return None

        return {
            "account_id": row.account_id,
            "company_name": row.company_name,
            "address": row.address,
            "business_type": row.business_type,
            "billing_method": row.billing_method,
            "discount_percent": row.discount_percent,
            "email": row.email,
        }
    finally:
        conn.close()


def create_business_account(
    company_name: str,
    address: str,
    business_type: str,
    billing_method: str,
    email: str,
) -> int:
    normalized_company_name = company_name.strip()
    normalized_address = address.strip()
    normalized_business_type = business_type.strip()
    normalized_email = email.strip().lower()

    missing_fields: list[str] = []

    if not normalized_company_name:
        missing_fields.append("company_name")

    if not normalized_address:
        missing_fields.append("address")

    if not normalized_business_type:
        missing_fields.append("business_type")

    if not normalized_email:
        missing_fields.append("email")

    if missing_fields:
        raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

    normalized_billing_method = normalize_billing_method(billing_method)
    discount_flag = 1 if normalized_billing_method == "credit_card" else 0

    conn = get_connection()
    conn.autocommit = False
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO BusinessAccounts
            (company_name, address, business_type, billing_method, discount_percent, email)
            OUTPUT INSERTED.account_id
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_company_name,
                normalized_address,
                normalized_business_type,
                normalized_billing_method,
                discount_flag,
                normalized_email,
            ),
        )

        row = cursor.fetchone()

        if row is None:
            raise RuntimeError("Failed to retrieve inserted account_id.")

        account_id = int(row[0])

        conn.commit()
        return account_id

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
