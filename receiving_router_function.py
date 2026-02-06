import json
import os
import pyodbc
import azure.functions as func
from openai import AzureOpenAI

# ------------------------
# Database utilities
# ------------------------

def get_db_connection():
    return pyodbc.connect(os.environ["SQL_CONNECTION_STRING"])

def get_customer_by_domain(domain):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            customer_id,
            onboarded,
            onboarding_status,
            authorized_emails
        FROM Customers
        WHERE email_domain = ?
    """, domain)

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "customer_id": row[0],
        "onboarded": bool(row[1]),
        "onboarding_status": row[2],
        "authorized_emails": row[3]
    }

def create_customer_stub(domain, sender_email):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO Customers (email_domain, primary_contact_email)
        VALUES (?, ?)
    """, domain, sender_email)

    conn.commit()
    conn.close()


# ------------------------
# Azure OpenAI / Foundry
# ------------------------

client = AzureOpenAI(
    api_key=os.environ["AZURE_OPENAI_KEY"],
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_version="2024-02-15-preview"
)

def call_onboarding_agent(context):
    response = client.chat.completions.create(
        model="onboarding-agent",
        messages=[
            {
                "role": "system",
                "content": "You are the Contoso onboarding agent. Collect missing customer information."
            },
            {
                "role": "user",
                "content": json.dumps(context)
            }
        ]
    )
    return response.choices[0].message.content

def call_orchestrator_agent(context):
    response = client.chat.completions.create(
        model="orchestrator-agent",
        messages=[
            {
                "role": "system",
                "content": "You are the Contoso orchestrator agent. Coordinate business workflows using other agents."
            },
            {
                "role": "user",
                "content": json.dumps(context)
            }
        ]
    )
    return response.choices[0].message.content


# ------------------------
# Main Router Entry Point
# ------------------------

def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Expected request body (from email system):
    {
        "from": "user@acme.com",
        "subject": "Quote request",
        "body": "We want pricing for item A and B"
    }
    """

    try:
        payload = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON payload", status_code=400)

    sender_email = payload.get("from")
    subject = payload.get("subject", "")
    message_body = payload.get("body", "")

    if not sender_email or "@" not in sender_email:
        return func.HttpResponse("Invalid sender email", status_code=400)

    domain = sender_email.split("@")[1].lower()

    # ------------------------
    # Customer lookup / creation
    # ------------------------

    customer = get_customer_by_domain(domain)

    if customer is None:
        # First-ever contact from this domain
        create_customer_stub(domain, sender_email)
        customer = get_customer_by_domain(domain)

    # ------------------------
    # Routing decision
    # ------------------------

    context = {
        "sender_email": sender_email,
        "email_domain": domain,
        "subject": subject,
        "message": message_body,
        "customer_state": customer
    }

    # Gate 1: Onboarding
    if not customer["onboarded"]:
        onboarding_reply = call_onboarding_agent(context)

        return func.HttpResponse(
            onboarding_reply,
            status_code=200,
            mimetype="text/plain"
        )

    # Gate 2: Fully onboarded → Orchestrator owns flow
    orchestrator_reply = call_orchestrator_agent(context)

    return func.HttpResponse(
        orchestrator_reply,
        status_code=200,
        mimetype="text/plain"
    )
