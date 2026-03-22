# Deploy Inventory MCP to Azure App Service (Linux) via Container

[Back to deployment index](README.md)

This runbook deploys the Inventory MCP as a **containerized web service** on Azure App Service for Linux, using:
- An **existing App Service Plan**: `asp-contoso-web-linux-b1` (B1, Linux)
- An **existing ACR**: `capstonemcpregistry2026`
- A **new Web App for Containers**: `admin-inventory-mcp`

All commands below are WSL-compatible and copy/paste-ready.

For repeat deployments after code changes, prefer the one-shot script:
- `scripts/deploy_inventory_mcp_appservice.sh`

---

## 0) Prereqs (one-time)

- WSL installed
- Docker installed and working inside WSL (Docker Desktop + WSL integration is fine)
- Azure CLI installed in WSL

Verify:

```bash
az version
docker version
```

---

## 1) Set variables (edit these first)

```bash
# REQUIRED: set this to your real subscription ID or exact subscription name.
# If you don't know it yet, run:
#   az account list --query "[].{name:name, id:id, isDefault:isDefault}" -o table
SUBSCRIPTION="Brad Lawrence - Visual Studio Enterprise"

# Resource group that contains your existing App Service Plan
RG="CapstoneSpring2026"

# Existing App Service plan (Linux B1)
PLAN="asp-contoso-web-linux-b1"

# Existing ACR name (NOT the login server)
ACR_NAME="capstonemcpregistry2026"

# Web App name (must be globally unique)
WEBAPP_NAME="admin-inventory-mcp"

# Container image naming
IMAGE_REPO="inventory-mcp"
IMAGE_TAG="$(date +%Y%m%d%H%M%S)"

# Runtime port your container listens on (matches Dockerfile default)
APP_PORT="8000"
```

---

## 2) Login + pick subscription

```bash
az login
az account set --subscription "$SUBSCRIPTION"
az account show --query "{name:name, id:id}" -o table
```

---

## 3) Confirm the existing plan exists (and is Linux)

```bash
az appservice plan show -g "$RG" -n "$PLAN" -o table
```

If this fails, either the resource group is wrong or the plan name is different.

---

## 4) Confirm ACR exists + get the login server

```bash
az acr show -n "$ACR_NAME" --query "{name:name, loginServer:loginServer, sku:sku.name}" -o table
ACR_LOGIN_SERVER="$(az acr show -n "$ACR_NAME" --query loginServer -o tsv)"

echo "ACR_LOGIN_SERVER=$ACR_LOGIN_SERVER"
```

---

## 5) Build the container image locally

From the repo root (where the top-level `Dockerfile` is):

```bash
docker build -t "$IMAGE_REPO:$IMAGE_TAG" .
```

Quick local smoke test:

```bash
docker run --rm -p 8000:8000 -e PORT=8000 "$IMAGE_REPO:$IMAGE_TAG"
# in another terminal:
curl -fsS http://localhost:8000/health
```

Stop the container with Ctrl+C.

---

## 6) Push the image to ACR

```bash
az acr login -n "$ACR_NAME"

FULL_IMAGE="$ACR_LOGIN_SERVER/$IMAGE_REPO:$IMAGE_TAG"
docker tag "$IMAGE_REPO:$IMAGE_TAG" "$FULL_IMAGE"
docker push "$FULL_IMAGE"

echo "Pushed: $FULL_IMAGE"
```

---

## 7) Create the Web App (Linux, container)

Check whether your webapp name is available:

```bash
az webapp list --query "[?name=='$WEBAPP_NAME'].{name:name, rg:resourceGroup}" -o table
```

If nothing returns, proceed to create.

```bash
az webapp create \
  -g "$RG" \
  -p "$PLAN" \
  -n "$WEBAPP_NAME" \
  -i "$FULL_IMAGE"
```

---

## 8) Allow App Service to pull from ACR

There are a few ways to do this; the steps below use the ACR admin user. If ACR admin is not allowed in your environment, configure the Web App to use a Managed Identity instead.

Enable ACR admin (if not already enabled):

```bash
az acr update -n "$ACR_NAME" --admin-enabled true
```

Configure the webapp with registry credentials:

```bash
ACR_USER="$(az acr credential show -n "$ACR_NAME" --query username -o tsv)"
ACR_PASS="$(az acr credential show -n "$ACR_NAME" --query passwords[0].value -o tsv)"

az webapp config container set \
  -g "$RG" \
  -n "$WEBAPP_NAME" \
  --docker-custom-image-name "$FULL_IMAGE" \
  --docker-registry-server-url "https://$ACR_LOGIN_SERVER" \
  --docker-registry-server-user "$ACR_USER" \
  --docker-registry-server-password "$ACR_PASS"
```

---

## 9) Set required App Settings (ports + health)

App Service needs to know which container port to route to:

```bash
az webapp config appsettings set \
  -g "$RG" \
  -n "$WEBAPP_NAME" \
  --settings \
    WEBSITES_PORT="$APP_PORT" \
    PORT="$APP_PORT" \
    MCP_ALLOWED_HOSTS="$WEBAPP_NAME.azurewebsites.net" \
    MCP_ALLOWED_ORIGINS="http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000" \
    SCM_DO_BUILD_DURING_DEPLOYMENT="false"

Notes:
- `MCP_ALLOWED_HOSTS` prevents deployed calls failing with `421 Invalid Host header`.
- If you use a custom domain, add it to `MCP_ALLOWED_HOSTS` (comma-separated).
```

(Optional) Configure health check path in the portal, or via CLI if available in your az version. Path should be:
- `/health`

---

## 9b) Connect to the real database (Azure SQL)

By default, this service uses an in-memory repository (you'll see `"product_name": "Test Item"`).
To use the real database, configure the Azure SQL connection string.

Set these App Settings on the Web App:
- `AZURE_SQL_CONNECTION_STRING`: ODBC connection string used by `pyodbc`
- `INVENTORY_REQUIRE_SQL=1`: recommended for deployments so the app fails fast if the DB config is missing

Example (replace placeholders; do not commit secrets):

```bash
AZURE_SQL_CONNECTION_STRING='Driver={ODBC Driver 18 for SQL Server};Server=tcp:<server>.database.windows.net,1433;Database=<db>;Uid=<user>;Pwd=<password>;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;'

az webapp config appsettings set \
  -g "$RG" \
  -n "$WEBAPP_NAME" \
  --settings \
    AZURE_SQL_CONNECTION_STRING="$AZURE_SQL_CONNECTION_STRING" \
    INVENTORY_REQUIRE_SQL="1"
```

### Azure SQL networking checklist

The container must be able to reach your SQL server over TCP/1433.

1) Get the Web App outbound IPs:

```bash
az webapp show -g "$RG" -n "$WEBAPP_NAME" --query outboundIpAddresses -o tsv
```

2) Ensure Azure SQL firewall rules allow the Web App to connect.

Options (pick one based on your team's security posture):
- Allow the Web App outbound IPs explicitly.
- Or (less strict) enable "Allow Azure services and resources to access this server" on the SQL server.
- If your SQL server uses a private endpoint, you must use VNet integration and test connectivity inside the VNet.

For local validation before deploying, see:
- [docs/inventory/real_sql_test.md](../inventory/real_sql_test.md)

---

## 10) Restart + verify

```bash
az webapp restart -g "$RG" -n "$WEBAPP_NAME"

BASE_URL="https://$WEBAPP_NAME.azurewebsites.net"

curl -fsS "$BASE_URL/health"; echo
```

MCP endpoint:
- `$BASE_URL/mcp`

---

## 11) Logs (when something goes wrong)

Enable container logging:

```bash
az webapp log config -g "$RG" -n "$WEBAPP_NAME" --docker-container-logging filesystem
```

Stream logs:

```bash
az webapp log tail -g "$RG" -n "$WEBAPP_NAME"
```
