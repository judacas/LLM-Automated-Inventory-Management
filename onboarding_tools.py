import json
import logging
import os
import pyodbc
from typing import Optional
from fastmcp import FastMCP
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()  # loads .env locally, ignored on PythonAnywhere (env vars set in Web tab)

logging.basicConfig(level=logging.INFO)


# ── DB Connection ──────────────────────────────────────────
def get_db_connection():
    return pyodbc.connect(
        f"Driver={{ODBC Driver 17 for SQL Server}};"  # 17 for PythonAnywhere, 18 for local
        f"Server={os.environ['DB_SERVER']},1433;"
        f"Database={os.environ['DB_NAME']};"
        f"Uid={os.environ['DB_USER']};"
        f"Pwd={os.environ['DB_PASSWORD']};"
        f"Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )


# ── Core Logic ─────────────────────────────────────────────
def check_domain_onboarded(domain: str) -> Optional[dict]:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT account_id, company_name, address, business_type,
                   billing_method, discount_percent, authorized_emails
            FROM dbo.BusinessAccounts
            WHERE domain         = ?
              AND company_name   IS NOT NULL
              AND address        IS NOT NULL
              AND business_type  IS NOT NULL
              AND billing_method IS NOT NULL
        """,
            (domain,),
        )
        row = cursor.fetchone()
    except Exception as e:
        logging.error(f"DB check failed for '{domain}': {e}")
        raise
    finally:
        conn.close()

    if not row:
        logging.info(f"Domain '{domain}' not onboarded.")
        return None

    return {
        "account_id": row[0],
        "company_name": row[1],
        "address": row[2],
        "business_type": row[3],
        "billing_method": row[4],
        "discount_percent": float(row[5]) if row[5] is not None else 0.0,
        "authorized_emails": json.loads(row[6]) if row[6] else [],
    }


# ── MCP Tool ───────────────────────────────────────────────
mcp = FastMCP("BusinessAccountsServer")


@mcp.tool()
def check_domain(domain: str) -> dict:
    """Check if a business domain is fully onboarded and return account info."""
    result = check_domain_onboarded(domain)
    if result is None:
        return {"onboarded": False, "message": f"Domain '{domain}' is not onboarded."}
    return {"onboarded": True, **result}


# ── ASGI App ───────────────────────────────────────────────
mcp_app = mcp.http_app(path="/")
app = FastAPI(lifespan=mcp_app.lifespan)
app.mount("/mcp", mcp_app)
