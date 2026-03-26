import azure.functions as func
import json
import logging
import os
import pyodbc
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

# Load .env only when running locally (not in Azure)
if "WEBSITE_HOSTNAME" not in os.environ:
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))


app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


# ── DB helpers ────────────────────────────────────────────────────────────────

def get_db_connection():
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={os.environ['DB_SERVER']};"
        f"DATABASE={os.environ['DB_NAME']};"
        f"UID={os.environ['DB_USER']};"
        f"PWD={os.environ['DB_PASSWORD']};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
        f"Connection Timeout=30;"
    )
    return pyodbc.connect(conn_str)


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
    Fires the onboarding agent using AIProjectClient with DefaultAzureCredential.
    Requires Azure AI User IAM role granted to the Function App managed identity.
    """
    project = AIProjectClient(
        endpoint=os.environ["ONBOARDING_AGENT_ENDPOINT"],
        credential=DefaultAzureCredential(),
    )

    openai_client = project.get_openai_client()

    response = openai_client.responses.create(
        input=[
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
        ],
        extra_body={
            "agent_reference": {
                "name":    os.environ["ONBOARDING_AGENT_NAME"],
                "version": os.environ["ONBOARDING_AGENT_VERSION"],
                "type":    "agent_reference"
            }
        },

    )


    logging.info(f"Onboarding agent response: {response.output_text}")


# ── Main route ────────────────────────────────────────────────────────────────

@app.route(route="email_receiver_router", auth_level=func.AuthLevel.FUNCTION)
def email_receiver_router(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Email router function received a request.")

    try:
        data = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON body", status_code=400)

    sender          = data.get("from", "")
    recipient       = data.get("to", "")
    subject         = data.get("subject", "")
    body            = data.get("body", "")
    has_attachments = data.get("hasAttachments", False)

    # ── Onboarding check ──────────────────────────────────────────────────────
    try:
        is_onboarded = check_domain_onboarded(sender)
    except Exception as e:
        logging.error(f"Database error during onboarding check: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Database error during onboarding check.", "details": str(e)}),
            status_code=500,
            mimetype="application/json"
        )

    if not is_onboarded:
        logging.info(f"'{sender}' not onboarded. Calling onboarding agent.")

        try:
            call_onboarding_agent(sender, subject, body)
        except Exception as e:
            logging.error(f"Onboarding agent call failed: {e}")
            return func.HttpResponse(
                json.dumps({"error": "Onboarding agent unavailable. Please try again later.", "details": str(e)}),
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
    logging.info(f"'{sender}' is onboarded. Routing email.")

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
