import json
from typing import Any, Dict, List, Optional

from mcp.database import get_connection


def get_business_by_domain(domain: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()

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
        WHERE domain = ?
        """,
        (domain,),
    )

    row = cursor.fetchone()
    conn.close()

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


def create_business_account(
    company_name: str,
    address: str,
    business_type: str,
    billing_method: str,
    domain: str,
    authorized_emails: List[str],
) -> int:
    conn = get_connection()
    conn.autocommit = False
    cursor = conn.cursor()

    try:
        emails_json = json.dumps(authorized_emails)

        discount_flag = 1 if billing_method == "credit_card" else 0
        
        # Insert into BusinessAccounts
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

        account_id: int = int(row[0])

        # Insert into AuthorizedEmails table
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