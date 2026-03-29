# Deployed Inventory MCP — Smoke Test (Streamable HTTP)

This runbook validates a deployed Inventory MCP instance over MCP **Streamable HTTP**.

## Prerequisites

- Python environment with dependencies installed (see repo `requirements.txt`).
- A deployed base URL.

## 1) Set the target URL

Set the deployed base URL and MCP endpoint.

```bash
BASE_URL="https://<your-app>.azurewebsites.net"
MCP_URL="$BASE_URL/mcp"
```

## 2) Verify the health endpoint

```bash
curl -fsS "$BASE_URL/health"; echo
```

Expected result:
- HTTP 200
- A short health payload (content may vary)

If this fails:
- Check the App Service logs.
- Confirm the container is listening on the configured port.

## 3) Verify MCP handshake + tools + tool calls

Run the built-in demo client against the deployed MCP endpoint:

```bash
python scripts/mcp_demo_client.py --url "$MCP_URL" --product-id 1001 --qty 3
```

If you recently changed server code, redeploy first using:

```bash
chmod +x scripts/deploy_inventory_mcp_appservice.sh
./scripts/deploy_inventory_mcp_appservice.sh
```

Expected output:
- A `TOOLS:` line listing at least:
  - `get_inventory`
  - `reserve_inventory`
  - `receive_inventory`
- Structured JSON-like responses printed after each call

Quick sanity check (mock vs real DB):
- If responses show `"product_name": "Test Item"`, you are still using the in-memory mock repository.
- For the real database, configure `AZURE_SQL_CONNECTION_STRING` on the Web App (see the deployment runbook).

## 4) Common failures

### 404 / Not Found

- Confirm the MCP path is `/mcp`.
- If you use `curl` without special headers, you may see `406 Not Acceptable` instead of `404`.
  - That still confirms the route exists; it just means your client didn’t advertise SSE support.
- If you do see `404`, double-check you’re hitting the correct app and the path is exactly `/mcp`.

### 406 `Not Acceptable: Client must accept text/event-stream`

This MCP server uses **Streamable HTTP**, which requires the client to accept **Server-Sent Events (SSE)**.

- If you call `$BASE_URL/mcp` from a browser or `curl` without the right `Accept` header, the server can return `406`.
- The demo client in this repo sets the correct headers automatically.

If you want to probe the endpoint with `curl` anyway:

```bash
curl -i -N -H "Accept: text/event-stream" "$MCP_URL"
```

Notes:
- This may still return `405 Method Not Allowed` depending on which methods the transport exposes.
- For a real end-to-end validation, prefer `python scripts/mcp_demo_client.py --url "$MCP_URL" ...`.

### MCP client error (`McpError`)

- Confirm the server is running the MCP ASGI app (not a legacy REST-only app).
- Confirm the endpoint is reachable from your network.

### Timeouts

- App Service can cold-start after being idle on some tiers.
- Re-run the health check once, then re-run the demo client.

### 421 `Invalid Host header`

This usually indicates host header validation rejecting the App Service hostname.

Actions:
- Redeploy the latest container image (the current codebase allow-lists the App Service hostname using MCP transport security settings).
- Re-test:
  - `python scripts/mcp_demo_client.py --url "$MCP_URL"`
