import azure.functions as func
import json
import logging
import os
import requests
import pyodbc

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


# ── DB helpers ────────────────────────────────────────────────────────────────

def get_db_connection():
    server   = os.environ["SQL_SERVER"]
    database = os.environ["SQL_DATABASE"]
    username = os.environ["SQL_USERNAME"]
    password = os.environ["SQL_PASSWORD"]

    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
        f"Connection Timeout=30;"
    )
    return pyodbc.connect(conn_str)


def get_domain(email: str) -> str:
    return email.split("@")[-1].lower() if "@" in email else ""

def check_domain_onboarded(domain: str) -> dict | None:
    try:
        conn   = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                account_id,
                company_name,
                address,
                business_type,
                billing_method,
                discount_percent,
                authorized_emails
            FROM dbo.BusinessAccounts
            WHERE domain          = ?
              AND company_name    IS NOT NULL
              AND address         IS NOT NULL
              AND business_type   IS NOT NULL
              AND billing_method  IS NOT NULL
        """, (domain,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            logging.info(f"Domain '{domain}' not onboarded or incomplete.")
            return None

        return {
            "account_id":        row[0],
            "company_name":      row[1],
            "address":           row[2],
            "business_type":     row[3],
            "billing_method":    row[4],
            "discount_percent":  float(row[5]) if row[5] else 0.0,
            "authorized_emails": json.loads(row[6]) if row[6] else []
        }

    except Exception as e:
        logging.error(f"DB check failed: {e}")
        raise
    

# ── Agent helpers ─────────────────────────────────────────────────────────────

def call_onboarding_agent(sender_email: str, subject: str, body: str) -> None:
    """
    Fires the onboarding agent with customer context.
    The agent handles the rest autonomously via its MCP tool:
      onboarding agent → MCP send_onboarding_email tool → email agent → customer
    No return value needed.
    """
    onboarding_agent_url = os.environ["ONBOARDING_AGENT_URL"]
    onboarding_agent_key = os.environ["ONBOARDING_AGENT_KEY"]

    payload = {
        "messages": [
            {
                "role": "user",
                "content": (
                    f"A new customer needs to be onboarded before receiving a quote.\n"
                    f"Sender Email: {sender_email}\n"
                    f"Subject: {subject}\n"
                    f"Message: {body}\n\n"
                    f"Please collect the following: company name, business address, "
                    f"type of business, authorized emails for purchase orders, "
                    f"and preferred billing method (credit card or mailed invoice)."
                )
            }
        ]
    }

    headers = {
        "Content-Type": "application/json",
        "api-key": onboarding_agent_key
    }

    response = requests.post(onboarding_agent_url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()


# ── Main route ────────────────────────────────────────────────────────────────

@app.route(route="email_receiver_router", auth_level=func.AuthLevel.FUNCTION)
def email_receiver_router(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Email router function received a request.")

    try:
        data = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON body", status_code=400)

    # Extract email fields
    sender          = data.get("from", "")
    recipient       = data.get("to", "")
    subject         = data.get("subject", "")
    body            = data.get("body", "")
    has_attachments = data.get("hasAttachments", False)

    # Validate sender
    domain = get_domain(sender)
    if not domain:
        return func.HttpResponse(
            json.dumps({"error": "Could not parse sender email domain."}),
            status_code=400,
            mimetype="application/json"
        )

    # ── Onboarding check ──────────────────────────────────────────────────────
    try:
        is_onboarded = check_domain_onboarded(domain)
    except Exception:
        return func.HttpResponse(
            json.dumps({"error": "Database error during onboarding check."}),
            status_code=500,
            mimetype="application/json"
        )

    if not is_onboarded:
        logging.info(f"Domain '{domain}' not onboarded. Calling onboarding agent.")

        try:
            call_onboarding_agent(sender, subject, body)
        except Exception as e:
            logging.error(f"Onboarding agent call failed: {e}")
            return func.HttpResponse(
                json.dumps({"error": "Onboarding agent unavailable. Please try again later."}),
                status_code=502,
                mimetype="application/json"
            )

        return func.HttpResponse(
            json.dumps({
                "status":  "onboarding_initiated",
                "message": "Onboarding process has been started. The customer will be contacted via email."
            }),
            status_code=200,
            mimetype="application/json"
        )

    # ── Domain is onboarded — route to quote agent ────────────────────────────
    logging.info(f"Domain '{domain}' is onboarded. Routing email.")

    return func.HttpResponse(
        json.dumps({
            "status":  "routed",
            "message": (
                f"Email received from {sender} to {recipient} "
                f"with subject '{subject}'. Attachments: {has_attachments}."
            )
        }),
        status_code=200,
        mimetype="application/json"
    )