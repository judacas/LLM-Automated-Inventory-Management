import os
import pymssql
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

def get_db_connection():
    return pymssql.connect(
        server=os.environ["DB_SERVER"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"]
    )

@app.route("/mcp", methods=["POST"])
def mcp_handler():
    body = request.get_json()
    method = body.get("method")
    params = body.get("params", {})
    req_id = body.get("id", 1)

    if method == "initialize":
        return jsonify({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "onboarding-mcp", "version": "1.0.0"}
            }
        })

    if method == "tools/list":
        return jsonify({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [{
                    "name": "check_domain",
                    "description": "Check if a domain is onboarded",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "domain": {"type": "string"}
                        },
                        "required": ["domain"]
                    }
                }]
            }
        })

    if method == "tools/call" and params.get("name") == "check_domain":
        domain = params.get("arguments", {}).get("domain", "")
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM BusinessAccounts WHERE domain = %s",
                (domain,)
            )
            count = cursor.fetchone()[0]
            conn.close()
            result = "onboarded" if count > 0 else "not onboarded"
            return jsonify({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"{domain} is {result}"}]
                }
            })
        except Exception as e:
            return jsonify({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": str(e)}
            })

    return jsonify({
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": "Method not found"}
    })

if __name__ == "__main__":
    port = int(os.environ.get("FUNCTIONS_CUSTOMHANDLER_PORT", 5000))
    app.run(host="0.0.0.0", port=port)
