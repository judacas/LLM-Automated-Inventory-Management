import logging
import os

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


def call_logic_app_1(email_payload):
    url = os.environ.get("LOGIC_APP_1_URL")
    if not url:
        logging.error("LOGIC_APP_1_URL not found in environment variables.")
        return None
    proxies = {"http": None, "https": None}
    try:
        response = requests.post(url, json=email_payload, proxies=proxies, timeout=20)
        response.raise_for_status()
        return {"success": True, "status": response.status_code}
    except Exception as e:
        logging.error(f"Logic App 1 API Call failed: {e}")
        return None


def call_logic_app_2(invoice_payload):
    url = os.environ.get("LOGIC_APP_2_URL")
    if not url:
        logging.error("LOGIC_APP_2_URL not found in environment variables.")
        return None
    proxies = {"http": None, "https": None}
    try:
        response = requests.post(url, json=invoice_payload, proxies=proxies, timeout=20)
        response.raise_for_status()
        return {"success": True, "status": response.status_code}
    except Exception as e:
        logging.error(f"Logic App 2 API Call failed: {e}")
        return None


@app.route("/mcp", methods=["POST"])
def mcp_handler():
    body = request.get_json()
    method = body.get("method")
    params = body.get("params", {})
    req_id = body.get("id", 1)

    if method == "initialize":
        return jsonify(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "email-sender-mcp", "version": "1.0.0"},
                },
            }
        )

    if method == "tools/list":
        return jsonify(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": "always_send_email",
                            "description": "Send a professional customer service email to the customer. Include invoice details in the body if a purchase was made.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "to": {
                                        "type": "string",
                                        "description": "Recipient email address",
                                    },
                                    "subject": {
                                        "type": "string",
                                        "description": "Email subject line",
                                    },
                                    "body": {
                                        "type": "string",
                                        "description": "Full email body content, including invoice details if applicable",
                                    },
                                },
                                "required": ["to", "subject", "body"],
                            },
                        },
                        {
                            "name": "shipping_department_sender",
                            "description": "Forward invoice details to the shipping department when a purchase has been made.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "subject": {
                                        "type": "string",
                                        "description": "Email subject line",
                                    },
                                    "body": {
                                        "type": "string",
                                        "description": "Invoice details to send to the shipping department",
                                    },
                                },
                                "required": ["subject", "body"],
                            },
                        },
                    ]
                },
            }
        )

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name == "always_send_email":
            if (
                not arguments.get("to")
                or not arguments.get("subject")
                or not arguments.get("body")
            ):
                return jsonify(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32602,
                            "message": "Missing required fields: 'to', 'subject', 'body'",
                        },
                    }
                ), 400
            result = call_logic_app_1(arguments)
            content_text = (
                f"Successfully sent email to {arguments.get('to')}."
                if result
                else "Failed to send email. Check logs for details."
            )
            return jsonify(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": content_text}]},
                }
            )

        if tool_name == "shipping_department_sender":
            if not arguments.get("subject") or not arguments.get("body"):
                return jsonify(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32602,
                            "message": "Missing required fields: 'subject', 'body'",
                        },
                    }
                ), 400
            result = call_logic_app_2(arguments)
            content_text = (
                "Successfully forwarded invoice to shipping department."
                if result
                else "Failed to send invoice to shipping department. Check logs for details."
            )
            return jsonify(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": content_text}]},
                }
            )

    return jsonify(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": "Method not found"},
        }
    )


# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=5000)
