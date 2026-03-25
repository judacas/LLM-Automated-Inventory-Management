#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# redeploy.sh — Rebuild and redeploy the Admin Portal to Azure App Service.
#
# Run this from the admin-portal/ directory in your WSL terminal:
#   cd admin-portal
#   chmod +x redeploy.sh   # first time only
#   ./redeploy.sh
#
# Prerequisites: az CLI, Docker (with WSL integration), logged-in az session.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Edit these three values to match your Azure resources ────────────────────
RG="CapstoneSpring2026"
WEBAPP="contoso-admin-portal-17079"   # your App Service web app name (NOT the plan)
ACR="contosoacr17079"
# ─────────────────────────────────────────────────────────────────────────────

ACR_LOGIN_SERVER="$(az acr show -n "$ACR" --query loginServer -o tsv)"
IMG_TAG="$(date +%Y%m%d-%H%M)"
FULL_IMAGE="$ACR_LOGIN_SERVER/contoso-admin-portal"

# Enable ACR admin user and fetch credentials so App Service can pull the image.
# This avoids needing RBAC role assignment permissions.
az acr update -n "$ACR" --admin-enabled true --output none
ACR_USERNAME="$(az acr credential show -n "$ACR" --query username -o tsv)"
ACR_PASSWORD="$(az acr credential show -n "$ACR" --query 'passwords[0].value' -o tsv)"

echo "══════════════════════════════════════════"
echo "  Contoso Admin Portal — Redeploy"
echo "  Image tag : $IMG_TAG"
echo "  Web app   : $WEBAPP  ($RG)"
echo "══════════════════════════════════════════"
echo ""

# 1 — Authenticate Docker to ACR
echo "[1/4] Logging in to ACR..."
az acr login -n "$ACR"

# 2 — Build image (must be run from admin-portal/ where the Dockerfile lives)
echo ""
echo "[2/4] Building image..."
docker build \
  -t "$FULL_IMAGE:$IMG_TAG" \
  -t "$FULL_IMAGE:latest" \
  .

# 3 — Push both tags
echo ""
echo "[3/4] Pushing image to ACR..."
docker push "$FULL_IMAGE:$IMG_TAG"
docker push "$FULL_IMAGE:latest"

# 4 — Update the App Service container config to the new timestamped tag.
#     Updating the config (rather than just restarting) guarantees Azure pulls
#     the new image rather than reusing its cached layer.
echo ""
echo "[4/4] Updating App Service container config (with registry credentials)..."
az webapp config container set \
  --name "$WEBAPP" \
  --resource-group "$RG" \
  --docker-custom-image-name "$FULL_IMAGE:$IMG_TAG" \
  --docker-registry-server-url "https://$ACR_LOGIN_SERVER" \
  --docker-registry-server-user "$ACR_USERNAME" \
  --docker-registry-server-password "$ACR_PASSWORD"

HOSTNAME="$(az webapp show --name "$WEBAPP" --resource-group "$RG" --query defaultHostName -o tsv)"

echo ""
echo "══════════════════════════════════════════"
echo "  Done!"
echo "  URL : https://$HOSTNAME/"
echo "══════════════════════════════════════════"
