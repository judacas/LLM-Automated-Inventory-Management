# Mock MCP Auth Binding Demo

This is an isolated demo that answers:

> Can the app layer bind a trusted user identity to the MCP client during an LLM call, so MCP enforces auth regardless of what the LLM says?

## What this demo contains

- Mock MCP server (in-memory only): `src/mock_mcp_auth_demo/server.py`
  - users list: `USERS`
  - permissions map: `PERMISSIONS`
  - tools:
    - `get_my_data`
    - `get_sensitive_data`
- ASGI app entrypoint: `src/mock_mcp_auth_demo/app.py`
- Foundry-style demo script: `scripts/mock_mcp_foundry_identity_demo.py`

## Where user identity is set (trusted source)

In the demo script, the application chooses identity in code via CLI args (defaults):

- `--authorized-user alice@example.com`
- `--unauthorized-user bob@example.com`

The script binds that trusted identity to MCP by constructing an HTTP client with:

- header: `x-demo-user: <trusted-user-email>`

The identity is never read from model output.

## How MCP client is bound to that user

In `scripts/mock_mcp_foundry_identity_demo.py`, each run creates:

- `httpx.AsyncClient(headers={"x-demo-user": trusted_identity})`
- `streamable_http_client(..., http_client=http_client)`

That means every MCP request in that session carries the app-selected identity.

## Where authorization is enforced

Authorization is enforced server-side in `src/mock_mcp_auth_demo/server.py`:

- `_trusted_user_from_context(ctx)` reads `x-demo-user` from request headers
- `_authorize(identity, tool_name)` checks `PERMISSIONS`
- tools call these checks before returning data

Unauthorized requests raise clear errors such as:

- `User 'bob@example.com' is not authorized to call tool 'get_sensitive_data'.`

## Run locally

From repository root:

```bash
python -m uvicorn mock_mcp_auth_demo.app:app --host 127.0.0.1 --port 8010 --app-dir src
```

In another terminal:

```bash
python scripts/mock_mcp_foundry_identity_demo.py --base-url http://127.0.0.1:8010
```

Expected behavior:

- `alice@example.com` succeeds for `get_my_data` and `get_sensitive_data`
- `bob@example.com` succeeds for `get_my_data` and is denied for `get_sensitive_data`

## Public endpoint via dev tunnels

Expose the local MCP server publicly (for Foundry-side testing):

```bash
devtunnel user login
devtunnel create mock-mcp-auth-demo -a
devtunnel port create -p 8010 --protocol http
devtunnel host mock-mcp-auth-demo
```

Then run the demo against the tunnel URL:

```bash
python scripts/mock_mcp_foundry_identity_demo.py --base-url https://<your-tunnel-host>
```

Note: for this issue, local credentials for real Foundry are optional; this mock demonstrates the same trust boundary pattern aligned with Foundry-style tool calling.
