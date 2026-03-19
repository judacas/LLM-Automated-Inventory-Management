import json

from typing_extensions import TypedDict

from database_tools.database import get_connection


class BusinessAccount(TypedDict):
    account_id: int
    company_name: str
    address: str
    business_type: str
    billing_method: str
    discount_percent: int
    authorized_emails: list[str]


def get_business_domains(limit: int = 10) -> list[str]:
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT TOP (?) domain
            FROM BusinessAccounts
            WHERE domain IS NOT NULL
            ORDER BY account_id
            """,
            (limit,),
        )

        rows = cursor.fetchall()
        return [str(row.domain) for row in rows]
    finally:
        conn.close()


def get_business_by_domain(domain: str) -> BusinessAccount | None:
    conn = get_connection()
    cursor = conn.cursor()

    try:
        normalized_domain = domain.strip().lower()

        cursor.execute(
            """
            SELECT account_id,
                   company_name,
                   address,
                   business_type,
                   billing_method,
                   discount_percent,
                   authorized_emails
            FROM BusinessAccounts
            WHERE LOWER(LTRIM(RTRIM(domain))) = ?
            """,
            (normalized_domain,),
        )

        row = cursor.fetchone()

        if not row:
            return None

        emails = json.loads(row.authorized_emails) if row.authorized_emails else []

        return {
            "account_id": row.account_id,
            "company_name": row.company_name,
            "address": row.address,
            "business_type": row.business_type,
            "billing_method": row.billing_method,
            "discount_percent": row.discount_percent,
            "authorized_emails": emails,
        }
    finally:
        conn.close()


def create_business_account(
    company_name: str,
    address: str,
    business_type: str,
    billing_method: str,
    domain: str,
    authorized_emails: list[str],
) -> int:
    conn = get_connection()
    conn.autocommit = False
    cursor = conn.cursor()

    try:
        emails_json = json.dumps(authorized_emails)

        discount_flag = 1 if billing_method == "credit_card" else 0

        cursor.execute(
            """
            INSERT INTO BusinessAccounts
            (company_name, address, business_type, billing_method, discount_percent, domain, authorized_emails)
            OUTPUT INSERTED.account_id
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company_name,
                address,
                business_type,
                billing_method,
                discount_flag,
                domain,
                emails_json,
            ),
        )

        row = cursor.fetchone()

        if row is None:
            raise RuntimeError("Failed to retrieve inserted account_id.")

        account_id = int(row[0])

        for email in authorized_emails:
            cursor.execute(
                """
                INSERT INTO AuthorizedEmails (account_id, email)
                VALUES (?, ?)
                """,
                (account_id, email),
            )

        conn.commit()
        return account_id

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
