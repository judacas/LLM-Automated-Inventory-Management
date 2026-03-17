# Deploy Inventory MCP to Azure Functions (Demo)

This runbook deploys the Inventory MCP server to an existing Azure Function App (Consumption plan, e.g. Y1) **without containers**.

## Hosting decision: Functions (recommended) vs App Service (B1)

You asked whether to deploy as:
- Azure Functions (serverless) using a Consumption-style plan (Y1) OR
- Azure App Service on a Linux Web App with a Basic (B1) App Service plan

Recommendation for this repo:
- Prefer **Azure Functions** for the inventory MCP demo because the project already includes a Functions HTTP trigger wrapper under `InventoryMcpProxy/`, and the ASGI app (`inventory_mcp.app:app`) was hardened specifically for the Functions ASGI adapter.

When you might prefer App Service B1 instead:
- You need **always-on** behavior and want to minimize cold-start impact.
- You expect longer-lived HTTP connections and want a traditional web hosting model.

Trade-off summary:
- **Functions**: simplest with this codebase, typically cheaper, but can cold start.
- **App Service B1**: steady always-on hosting, but higher fixed monthly cost and requires additional webapp-specific deployment config.

## What gets deployed

- A single Azure Functions HTTP Trigger that forwards all HTTP routes to the existing ASGI app (`inventory_mcp.app:app`).
- Endpoints after deployment:
  - `GET /health`
  - MCP Streamable HTTP endpoint: `/mcp`

Implementation notes:
- `host.json` sets `routePrefix` to `""`, so routes are **not** prefixed with `/api`.
- `InventoryMcpProxy/` is the Azure Functions trigger folder.

Best-practice note:
- For brand-new production apps, Azure guidance generally prefers **Flex Consumption (FC1)** for Functions.
- For a time-boxed demo, an existing **Consumption/Y1** Function App is fine.

## Prerequisites

- Azure CLI installed (`az`)
- Azure Functions Core Tools installed (`func`)
- You know:
  - Function App name (example: `my-inventory-func`)
  - Resource group name (example: `rg-inventory-demo`)

Optional (recommended) for a quick local smoke test:
- Python venv at `.venv` and `pip install -r requirements.txt`

## 0) Pre-deploy checklist (do this once)

Before you publish, do a fast local validation so you don’t discover issues on Azure:

1) Run the "Final pre-deploy smoke test" in [docs/run_inventory_mcp.md](run_inventory_mcp.md)
2) (Recommended) Run the Azure Functions local-host test in that same doc
3) Ensure your deployment assumption is correct:
  - If you are demoing **mock inventory** only: do NOT set `AZURE_SQL_CONNECTION_STRING` in Azure.
  - If you are demoing **real SQL**: confirm you have an ODBC driver available and the DB schema exists.

## 1) Login and select subscription

```bash
az login
az account set --subscription <SUBSCRIPTION_ID_OR_NAME>
```

## 1.5) If you do NOT have a Function App yet (create one)

Skip this section if you already have a working Function App to publish to.

Best practice note:
- For brand-new deployments, Azure guidance typically recommends **Flex Consumption (FC1)** for Functions.
- This runbook focuses on publishing code to an existing Function App. If you must create new infra from scratch, prefer using an AZD/Bicep template that provisions FC1 correctly.
- References (examples of FC1 infra patterns):
  - https://github.com/Azure-Samples/functions-quickstart-javascript-azd/tree/main/infra
  - https://github.com/Azure-Samples/functions-quickstart-dotnet-azd-eventgrid-blob/tree/main/infra

Choose names (must be globally unique where noted):
- `<RESOURCE_GROUP>`: e.g. `rg-inventory-demo`
- `<LOCATION>`: e.g. `eastus`
- `<STORAGE_ACCOUNT>` (globally unique, lowercase letters/numbers only)
- `<FUNCTION_APP_NAME>` (globally unique)

### Bash/WSL

```bash
az group create -n <RESOURCE_GROUP> -l <LOCATION>

az storage account create \
  -n <STORAGE_ACCOUNT> \
  -g <RESOURCE_GROUP> \
  -l <LOCATION> \
  --sku Standard_LRS

# Demo-only quickstart: creates a Linux Consumption (Y1) Function App for Python.
# Prefer Flex Consumption (FC1) for brand-new apps when feasible.
az functionapp create \
  -g <RESOURCE_GROUP> \
  -n <FUNCTION_APP_NAME> \
  --storage-account <STORAGE_ACCOUNT> \
  --consumption-plan-location <LOCATION> \
  --functions-version 4 \
  --runtime python \
  --runtime-version 3.11 \
  --os-type Linux
```

### PowerShell (no line continuations)

```powershell
az group create -n <RESOURCE_GROUP> -l <LOCATION>
az storage account create -n <STORAGE_ACCOUNT> -g <RESOURCE_GROUP> -l <LOCATION> --sku Standard_LRS
az functionapp create -g <RESOURCE_GROUP> -n <FUNCTION_APP_NAME> --storage-account <STORAGE_ACCOUNT> --consumption-plan-location <LOCATION> --functions-version 4 --runtime python --runtime-version 3.11 --os-type Linux
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

### Remote build (recommended if dependency install fails)

If publish fails because dependencies are missing on Azure, ensure remote build is enabled:

```bash
az functionapp config appsettings set \
  --name <FUNCTION_APP_NAME> \
  --resource-group <RESOURCE_GROUP> \
  --settings SCM_DO_BUILD_DURING_DEPLOYMENT=1 ENABLE_ORYX_BUILD=1
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

Expected:
- `/health` returns `200` with `{ "status": "ok" }`
- `/mcp` should *not* 404. (It may return a non-200 to `GET` since MCP is typically `POST`-driven, but it should be reachable.)

### (Recommended) Verify tool calls end-to-end

Use the included Python demo client against Azure:

```bash
uv run python scripts/mcp_demo_client.py --url https://<FUNCTION_APP_NAME>.azurewebsites.net/mcp --product-id 1001 --qty 3
```

This validates:
- CORS-independent tool calls (server-side client)
- MCP initialize + list_tools + call_tool
- Your Function App routing/forwarding logic

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
  - Confirm you deployed the MCP Function App code (not the legacy REST API archived under `legacy/`).
  - Check Function App logs:

```bash
az functionapp log tail --name <FUNCTION_APP_NAME> --resource-group <RESOURCE_GROUP>
```

- If Inspector says “proxy token incorrect”:
  - Copy the **latest** token from the Inspector terminal (restart → new token).
