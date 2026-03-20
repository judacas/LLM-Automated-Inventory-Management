import os
import logging
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


def call_email_api(email_payload):
    url = os.environ.get("LOGIC_APP_URL")
    if not url:
        logging.error("LOGIC_APP_URL not found in environment variables.")
        return None
    proxies = {"http": None, "https": None}
    try:
        response = requests.post(url, json=email_payload, proxies=proxies, timeout=20)
        response.raise_for_status()
        return {"success": True, "status": response.status_code}
    except Exception as e:
        logging.error(f"Logic App API Call failed: {e}")
        return None


@app.route("/mcp", methods=["POST"])
def mcp_handler():
    body = request.get_json()
    method = body.get("method")
    params = body.get("params", {})
    req_id = body.get("id", 1)

    if method == "initialize":
        return jsonify({
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "email-sender-mcp", "version": "1.0.0"}
            }
        })

    if method == "tools/list":
        return jsonify({
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "tools": [{
                    "name": "email_sender",
                    "description": "Send a professional email via the business logic workflow.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "email": {
                                "type": "object",
                                "description": "The email details",
                                "properties": {
                                    "to": {"type": "string", "description": "Recipient address"},
                                    "subject": {"type": "string", "description": "Email subject line"},
                                    "body": {"type": "string", "description": "Main message content"}
                                },
                                "required": ["to", "subject", "body"]
                            }
                        },
                        "required": ["email"]
                    }
                }]
            }
        })

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        if tool_name == "email_sender":
            email_info = arguments.get("email")
            if not email_info:
                return jsonify({
                    "jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32602, "message": "Missing 'email' argument"}
                }), 400
            result = call_email_api(email_info)
            content_text = (
                f"Successfully sent email to {email_info.get('to')}."
                if result else "Failed to send email. Check logs for details."
            )
            return jsonify({
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": content_text}]}
            })

    return jsonify({
        "jsonrpc": "2.0", "id": req_id,
        "error": {"code": -32601, "message": "Method not found"}
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
