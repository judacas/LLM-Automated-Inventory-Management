# Mock auth-bound MCP demo

This demo shows how an application can bind a **trusted user identity** to an MCP
client so that the server enforces authorization regardless of any LLM output.

## What this contains
- `src/mock_auth_mcp`: isolated mock MCP server with in-memory users/permissions
- Tools: `get_my_data`, `get_sensitive_data`
- Server-side auth: checks the user identity passed in the MCP session/request
- `scripts/mock_auth_identity_demo.py`: runs authorized and unauthorized calls

## Where identity is set
- In the demo script, the app picks an identity (e.g. `alice@example.com`) and
  binds it to the MCP client via `Implementation(..., user=<trusted_user>)` when
  constructing `ClientSession`. The LLM never gets to decide the identity.

## Where MCP enforces auth
- `mock_auth_mcp.server.resolve_identity` pulls the bound identity from
  `ClientSession.client_info` (or request `meta`) and rejects missing identities.
- `mock_auth_mcp.server.require_permission` enforces per-tool permissions
  (`get_sensitive_data` requires the `sensitive` permission).

## Run the mock MCP server
```bash
uv run uvicorn mock_auth_mcp.app:app --reload --host 0.0.0.0 --port 8011
```

Health check: `curl -s http://localhost:8011/health`

## Make the server reachable via a tunnel (optional)
- `azd tunnel --target-port 8011` (Azure dev tunnel), or
- `ngrok http 8011`

Update the demo URL to the public tunnel URL so external clients can reach it.

## Run the identity-binding demo
```bash
uv run python scripts/mock_auth_identity_demo.py --url http://localhost:8011/mcp
```

What it shows:
- **Authorized** (`alice@example.com`): `get_sensitive_data` succeeds.
- **Unauthorized** (`bob@example.com`): the server denies `get_sensitive_data`
  even if the (mock) model requests it, because the bound identity lacks the
  permission.

You can also pass a single identity:
```bash
uv run python scripts/mock_auth_identity_demo.py --url http://localhost:8011/mcp --identity bob@example.com
```
