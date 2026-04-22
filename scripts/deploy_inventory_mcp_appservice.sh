#!/usr/bin/env bash
set -euo pipefail

# Redeploy Inventory MCP to an existing Azure App Service (Linux) Web App for Containers.
#
# This script is intended for *repeat deployments* after code changes.
# It assumes the Web App already exists and is already configured to pull from ACR.
#
# Required environment variables:
#   SUBSCRIPTION   Azure subscription name or ID
#   RG             Resource group name
#   ACR_NAME        Azure Container Registry name (not login server)
#   WEBAPP_NAME     App Service Web App name (Linux container)
#
# Optional environment variables:
#   IMAGE_REPO      Image repo name in ACR (default: inventory-mcp)
#   IMAGE_TAG       Image tag (default: timestamp)
#   APP_PORT        Container port App Service should route to (default: 8000)
#   SET_ACR_CREDS   Set to 1 to (re)configure ACR admin creds on the Web App
#                  (requires ACR admin enabled; avoid if you use Managed Identity)
#   AZURE_SQL_CONNECTION_STRING
#                  If set, the script will configure the Web App to use the
#                  real SQL-backed repositories.
#   INVENTORY_REQUIRE_SQL
#                  If set to 1/true/yes/on, the server will refuse to start
#                  unless AZURE_SQL_CONNECTION_STRING is configured.
#
# Examples (WSL):
#   export SUBSCRIPTION="Brad Lawrence - Visual Studio Enterprise"
#   export RG="CapstoneSpring2026"
#   export ACR_NAME="capstonemcpregistry2026"
#   export WEBAPP_NAME="admin-inventory-mcp"
#   ./scripts/deploy_inventory_mcp_appservice.sh

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

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing dependency: $1" >&2
    exit 1
  fi
}

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required env var: $name" >&2
    exit 1
  fi
}

require_cmd az
require_cmd docker
require_cmd date

require_env SUBSCRIPTION
require_env RG
require_env ACR_NAME
require_env WEBAPP_NAME

IMAGE_REPO="${IMAGE_REPO:-inventory-mcp}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}"
APP_PORT="${APP_PORT:-8000}"

az account set --subscription "$SUBSCRIPTION" >/dev/null

ACR_LOGIN_SERVER="$(az acr show -n "$ACR_NAME" --query loginServer -o tsv)"
FULL_IMAGE="$ACR_LOGIN_SERVER/$IMAGE_REPO:$IMAGE_TAG"

echo "Building image..."
docker build -t "$IMAGE_REPO:$IMAGE_TAG" .

echo "Logging into ACR..."
az acr login -n "$ACR_NAME" >/dev/null

echo "Pushing image: $FULL_IMAGE"
docker tag "$IMAGE_REPO:$IMAGE_TAG" "$FULL_IMAGE"
docker push "$FULL_IMAGE" >/dev/null

echo "Updating Web App container image..."
az webapp config container set \
  -g "$RG" \
  -n "$WEBAPP_NAME" \
  --docker-custom-image-name "$FULL_IMAGE" \
  --docker-registry-server-url "https://$ACR_LOGIN_SERVER" \
  >/dev/null

if [[ "${SET_ACR_CREDS:-0}" == "1" ]]; then
  echo "SET_ACR_CREDS=1: configuring registry credentials on the Web App (ACR admin user)."
  ACR_USER="$(az acr credential show -n "$ACR_NAME" --query username -o tsv)"
  ACR_PASS="$(az acr credential show -n "$ACR_NAME" --query passwords[0].value -o tsv)"

  az webapp config container set \
    -g "$RG" \
    -n "$WEBAPP_NAME" \
    --docker-custom-image-name "$FULL_IMAGE" \
    --docker-registry-server-url "https://$ACR_LOGIN_SERVER" \
    --docker-registry-server-user "$ACR_USER" \
    --docker-registry-server-password "$ACR_PASS" \
    >/dev/null
fi

echo "Setting app settings (ports)..."
APP_SETTINGS=(
  "WEBSITES_PORT=$APP_PORT"
  "PORT=$APP_PORT"
  "MCP_ALLOWED_HOSTS=$WEBAPP_NAME.azurewebsites.net"
  "MCP_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"
  "SCM_DO_BUILD_DURING_DEPLOYMENT=false"
)

if [[ -n "${AZURE_SQL_CONNECTION_STRING:-}" ]]; then
  echo "Configuring AZURE_SQL_CONNECTION_STRING (SQL-backed repositories enabled)."
  APP_SETTINGS+=("AZURE_SQL_CONNECTION_STRING=$AZURE_SQL_CONNECTION_STRING")
  # Default to requiring SQL when a connection string is provided.
  APP_SETTINGS+=("INVENTORY_REQUIRE_SQL=${INVENTORY_REQUIRE_SQL:-1}")
else
  echo "NOTE: AZURE_SQL_CONNECTION_STRING is not set in your shell; deploying with mock/in-memory repository." >&2
  # Keep requirement off unless explicitly requested.
  if [[ -n "${INVENTORY_REQUIRE_SQL:-}" ]]; then
    APP_SETTINGS+=("INVENTORY_REQUIRE_SQL=$INVENTORY_REQUIRE_SQL")
  fi
fi

az webapp config appsettings set \
  -g "$RG" \
  -n "$WEBAPP_NAME" \
  --settings "${APP_SETTINGS[@]}" \
  >/dev/null

echo "Restarting Web App..."
az webapp restart -g "$RG" -n "$WEBAPP_NAME" >/dev/null

BASE_URL="https://$WEBAPP_NAME.azurewebsites.net"

echo "Health check: $BASE_URL/health"
curl -fsS "$BASE_URL/health"; echo

echo "MCP endpoint check (should not be 421 Invalid Host header): $BASE_URL/mcp"
# Note: Streamable HTTP expects SSE; probing with Accept header avoids misleading 406s.
# We also cap the request time because SSE may keep the connection open.
curl -i -sS --max-time 3 -H "Accept: text/event-stream" "$BASE_URL/mcp" | head -n 20 || true

echo "Done: $FULL_IMAGE"
