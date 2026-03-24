# Inventory MCP: Real SQL Test (WSL)

This guide validates that Inventory MCP is using the **SQL-backed repositories** instead of mock/in-memory storage.

## Important

- Do not commit connection strings.
- Use environment variables in your shell session.

## Prerequisites

1) A reachable SQL Server / Azure SQL database
- Network access must allow connections from your machine.
- If using Azure SQL, confirm firewall rules allow your current public IP.

2) ODBC driver available in WSL

The Inventory MCP uses `pyodbc`, which requires an ODBC driver.
For Ubuntu-based WSL, the common choice is Microsoft ODBC Driver 18.

If you do not have it installed, install it using Microsoft’s official Linux instructions for:
- Microsoft ODBC Driver 18 for SQL Server
- unixODBC

## Step 1 — Start Inventory MCP with SQL enabled

From repo root:

```bash
uv sync
export PYTHONPATH=src

# Recommended: copy the **ODBC** connection string from the Azure Portal
# (SQL server → Connection strings) and paste it here, replacing ONLY the password.
# The values for Server/Database/User should match what Azure shows you.
#
# Notes on `{}` in ODBC connection strings:
# - `{}` is required around the Driver name (example: `{ODBC Driver 18 for SQL Server}`)
# - For `Pwd=...`, `{}` is optional and only needed if your password contains
#   special characters that would confuse parsing (especially `;`).
#
# Example only. Do not commit real secrets.
export AZURE_SQL_CONNECTION_STRING='Driver={ODBC Driver 18 for SQL Server};Server=tcp:<server>.database.windows.net,1433;Database=<db>;Uid=<user>;Pwd=<password>;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;'

uv run uvicorn inventory_mcp.app:app --reload --host 0.0.0.0 --port 8000
```

If your password contains a single quote (`'`), avoid inline single-quoting and use a heredoc instead:

```bash
export AZURE_SQL_CONNECTION_STRING="$(cat <<'EOF'
Driver={ODBC Driver 18 for SQL Server};Server=tcp:<server>.database.windows.net,1433;Database=<db>;Uid=<user>;Pwd=<password>;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;
EOF
)"
```

## Step 2 — Validate tool behavior via demo client

In a second terminal:

```bash
uv run python scripts/mcp_demo_client.py --url http://localhost:8000/mcp --product-id 1001 --qty 1
```

Expected:
- Tool list prints
- `get_inventory` returns data for your real DB product rows

## Step 3 — Validate the additional admin tools

To validate the admin monitoring tools (including `get_all_inventory`), use the same demo client.
It will call additional tools when they are available on the server.

## Troubleshooting

- `pyodbc.Error: [unixODBC]` / driver not found:
  - Install the Microsoft ODBC driver in WSL and confirm `odbcinst -q -d` lists it.

- `HYT00` / `Login timeout expired` (example: `[Microsoft][ODBC Driver 18 for SQL Server]Login timeout expired`):
  - This usually means the client could not establish a network connection to the SQL endpoint (not a credential error yet).

  Checklist:
  1) Verify the server hostname is correct
    - Azure SQL format is typically: `<server>.database.windows.net`
    - Make sure you did not include `https://` in the `Server=` value.

  2) Check DNS resolution from WSL
    - Run: `nslookup <server>.database.windows.net`
    - If DNS fails, you may be on a network/VPN configuration that blocks resolution.

  3) Check port 1433 reachability from WSL
    - Run one of the following:
     - `nc -vz <server>.database.windows.net 1433`
     - or: `timeout 5 bash -c 'cat < /dev/null > /dev/tcp/<server>.database.windows.net/1433'`
    - If this fails, a firewall or network policy is blocking outbound 1433.

  4) Azure SQL firewall rules
    - In the Azure Portal: SQL server → Networking → Public access
    - Ensure your current public IP is allowed.
    - If you are on campus/VPN, your public IP may change; re-check before testing.
    - To find your public IP (WSL): `curl -s ifconfig.me`

  5) Private endpoint / VNet integration
    - If the database uses a private endpoint, it is not reachable from a typical local machine.
    - In that case you must test from a machine inside the VNet (or via approved private connectivity).

- Login or network failures:
  - Re-check username/password and firewall/network rules.

## Retest after fixing connectivity

Once DNS + port reachability are confirmed, restart the Inventory MCP process and rerun:

```bash
uv run python scripts/mcp_demo_client.py --url http://localhost:8000/mcp --product-id 1001 --qty 1
```
