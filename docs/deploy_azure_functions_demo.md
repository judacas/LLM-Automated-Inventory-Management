# Deploy Inventory MCP to Azure Functions (Demo)

This runbook deploys the Inventory MCP server to an existing Azure Function App (Consumption plan, e.g. Y1) **without containers**.

## What gets deployed

- A single Azure Functions HTTP Trigger that forwards all HTTP routes to the existing ASGI app (`inventory_mcp.app:app`).
- Endpoints after deployment:
  - `GET /health`
  - MCP Streamable HTTP endpoint: `/mcp`

Implementation notes:
- `host.json` sets `routePrefix` to `""`, so routes are **not** prefixed with `/api`.
- `InventoryMcpProxy/` is the Azure Functions trigger folder.

## Prerequisites

- Azure CLI installed (`az`)
- Azure Functions Core Tools installed (`func`)
- You know:
  - Function App name (example: `my-inventory-func`)
  - Resource group name (example: `rg-inventory-demo`)

## 1) Login and select subscription

```bash
az login
az account set --subscription <SUBSCRIPTION_ID_OR_NAME>
```

## 2) (Recommended) Configure demo-friendly app settings

### CORS for Inspector

The MCP Inspector UI runs in your browser from a localhost origin (often `http://localhost:5173`).
Your Function App is a different origin, so the browser will enforce CORS.

Demo option (permissive):

```bash
az functionapp config appsettings set \
  --name <FUNCTION_APP_NAME> \
  --resource-group <RESOURCE_GROUP> \
  --settings MCP_CORS_ORIGINS="*"
```

Safer local-only option:

```bash
az functionapp config appsettings set \
  --name <FUNCTION_APP_NAME> \
  --resource-group <RESOURCE_GROUP> \
  --settings MCP_CORS_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"
```

## 3) Publish the code

From the repo root:

```bash
func azure functionapp publish <FUNCTION_APP_NAME> --python --build remote
```

Notes:
- `--build remote` is recommended so Azure builds wheels/server-side in a consistent environment.
- Your team’s Y1 plan works for a demo, but longer-term Azure guidance typically recommends Flex Consumption (FC1) for new apps.

## 4) Smoke test

After publish completes:

```bash
curl -i https://<FUNCTION_APP_NAME>.azurewebsites.net/health
```

Then verify MCP endpoint is reachable:

```bash
curl -i https://<FUNCTION_APP_NAME>.azurewebsites.net/mcp
curl -i https://<FUNCTION_APP_NAME>.azurewebsites.net/mcp/
```

## 5) Demo with MCP Inspector

1) Start the Inspector locally:

```bash
npx -y @modelcontextprotocol/inspector
```

2) In the Inspector UI:
- Paste the **proxy token** shown in your Inspector terminal (the token changes every time you restart Inspector)
- Connect to:
  - `https://<FUNCTION_APP_NAME>.azurewebsites.net/mcp`

## Troubleshooting

- If `/health` works but `/mcp` fails:
  - Confirm you deployed the MCP Function App code (not the legacy `tool_api`).
  - Check Function App logs:

```bash
az functionapp log tail --name <FUNCTION_APP_NAME> --resource-group <RESOURCE_GROUP>
```

- If Inspector says “proxy token incorrect”:
  - Copy the **latest** token from the Inspector terminal (restart → new token).
