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


def check_email_onboarded(email: str) -> dict | None:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                company_name,
                address,
                business_type,
                billing_method
            FROM dbo.BusinessAccounts
            WHERE email           = ?
              AND company_name    IS NOT NULL
              AND address         IS NOT NULL
              AND business_type   IS NOT NULL
              AND billing_method  IS NOT NULL
        """,
            (email,),
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            logging.info(f"Email '{email}' not onboarded or incomplete.")
            return None

        return {
            "email": email,
            "company_name": row[0],
            "address": row[1],
            "business_type": row[2],
            "billing_method": row[3],
        }

    except Exception as e:
        logging.error(f"DB check failed: {e}")
        raise


# ── Agent helpers ─────────────────────────────────────────────────────────────


def call_onboarding_agent(sender_email: str, subject: str, body: str) -> str:
    """
    Calls the userOnboarding agent in Azure AI Foundry.
    Uses ONBOARDING_AGENT_ENDPOINT, ONBOARDING_AGENT_NAME, ONBOARDING_AGENT_VERSION
    from environment variables.
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
                    f"Sender Email: {sender_email}\n"
                    f"Subject: {subject}\n"
                    f"Message: {body}\n\n"
                ),
            }
        ],
        extra_body={
            "agent_reference": {
                "name": os.environ["ONBOARDING_AGENT_NAME"],
                "version": os.environ["ONBOARDING_AGENT_VERSION"],
                "type": "agent_reference",
            }
        },
    )

    logging.info(f"Onboarding agent response: {response.output_text}")
    return response.output_text


def call_orchestrator_agent(sender_email: str, subject: str, body: str) -> str:
    """
    Calls the userOrchestrator agent in Azure AI Foundry for fully onboarded customers.
    Uses ORCHESTRATOR_AGENT_ENDPOINT, ORCHESTRATOR_AGENT_NAME, ORCHESTRATOR_AGENT_VERSION
    from environment variables.
    """
    project = AIProjectClient(
        endpoint=os.environ["ORCHESTRATOR_AGENT_ENDPOINT"],
        credential=DefaultAzureCredential(),
    )

    openai_client = project.get_openai_client()

    response = openai_client.responses.create(
        input=[
            {
                "role": "user",
                "content": (
                    f"--- Incoming Email ---\n"
                    f"Sender Email:    {sender_email}\n"
                    f"Subject:          {subject}\n"
                    f"Message:\n{body}"
                ),
            }
        ],
        extra_body={
            "agent_reference": {
                "name": os.environ["ORCHESTRATOR_AGENT_NAME"],
                "version": os.environ["ORCHESTRATOR_AGENT_VERSION"],
                "type": "agent_reference",
            }
        },
    )

    logging.info(f"Orchestrator agent response: {response.output_text}")
    return response.output_text


# ── Main route ────────────────────────────────────────────────────────────────


@app.route(route="email_receiver_router", auth_level=func.AuthLevel.FUNCTION)
def email_receiver_router(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Email router function received a request.")

    try:
        data = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON body", status_code=400)

    sender = data.get("from", "")
    subject = data.get("subject", "")
    body = data.get("body", "")
    has_attachments = data.get("hasAttachments", False)

    # ── Onboarding check ──────────────────────────────────────────────────────
    try:
        account = check_email_onboarded(sender)
    except Exception as e:
        logging.error(f"Database error during onboarding check: {e}")
        return func.HttpResponse(
            json.dumps(
                {"error": "Database error during onboarding check.", "details": str(e)}
            ),
            status_code=500,
            mimetype="application/json",
        )

    # ── NOT onboarded → call userOnboarding agent ─────────────────────────────
    if not account:
        logging.info(f"'{sender}' not onboarded. Calling onboarding agent.")
        try:
            agent_response = call_onboarding_agent(sender, subject, body)
        except Exception as e:
            logging.error(f"Onboarding agent call failed: {e}")
            return func.HttpResponse(
                json.dumps(
                    {"error": "Onboarding agent unavailable.", "details": str(e)}
                ),
                status_code=502,
                mimetype="application/json",
            )

        return func.HttpResponse(
            json.dumps(
                {
                    "status": "onboarding_initiated",
                    "message": "Onboarding process started. Customer will be contacted via email.",
                    "agent_response": agent_response,
                }
            ),
            status_code=200,
            mimetype="application/json",
        )

    # ── Onboarded → call userOrchestrator agent ───────────────────────────────
    logging.info(f"'{sender}' is onboarded. Calling orchestrator agent.")
    try:
        agent_response = call_orchestrator_agent(sender, subject, body)
    except Exception as e:
        logging.error(f"Orchestrator agent call failed: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Orchestrator agent unavailable.", "details": str(e)}),
            status_code=502,
            mimetype="application/json",
        )

    return func.HttpResponse(
        json.dumps(
            {
                "status": "routed",
                "message": f"Email from '{sender}' routed to orchestrator agent.",
                "agent_response": agent_response,
            }
        ),
        status_code=200,
        mimetype="application/json",
    )
