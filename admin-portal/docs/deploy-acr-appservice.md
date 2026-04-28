# Deploy Admin Portal (ACR + Azure App Service for Containers)

This guide deploys the **Admin Portal UI** (Node.js/Express + static frontend) as a Linux container image in **Azure App Service**, pulling from your **Azure Container Registry (ACR)**.

## Your resources

- ACR: `contosoacr17079`
- Resource Group: `CapstoneSpring2026`
- App Service Plan (Linux, B1): `asp-contoso-web-linux-b1`
- Web App: set `WEBAPP` in the commands / script below

> Run the commands below in your **WSL terminal**.

---

## ⚡ Quick Redeploy (use this after every code change)

A script handles the full build-push-deploy cycle. Edit the two config lines at the top of the script once, then just run it every time you have changes:

```bash
# 1. Open the script (from the repo root) and set WEBAPP to your web app name
#    (see Section 1 below if you need to look it up)
code admin-portal/redeploy.sh      # or nano / any editor

# 2. From the admin-portal/ directory in WSL:
cd admin-portal
chmod +x redeploy.sh               # first time only
./redeploy.sh
```

The script will:

1. Login to ACR
2. Build a new image with a timestamp tag (e.g. `20260325-1430`) and `:latest`
3. Push both tags to ACR
4. Update the App Service container config to the new tag — this forces Azure to pull the new image immediately (a plain `restart` does **not** guarantee a fresh pull)

**Environment variables never need to be re-pushed** — they are managed in the Azure Portal (App Service → Settings → Environment variables) and survive redeployments.

---

## First-Time Setup

Follow these steps once when provisioning from scratch.

---

### 0) Prerequisites (one-time)

1. Install/verify:
   - Azure CLI (`az`)
   - Docker (Docker Desktop + WSL integration)

2. Sign in:

```bash
az login
```

1. Select the right subscription (if needed):

```bash
az account show
az account set --subscription "<SUBSCRIPTION_ID_OR_NAME>"
```

---

### 1) Find your Web App name

`asp-contoso-web-linux-b1` is the **App Service Plan** (compute resource), not the web app (the actual site). The deploy commands need the web app name.

```bash
# List web apps in the resource group
az webapp list -g "CapstoneSpring2026" -o table
```

If you already have a web app, set:

```bash
export RG="CapstoneSpring2026"
export WEBAPP="<YOUR_WEB_APP_NAME>"         # from the list above
```

If you do **not** have a web app yet, create one (pick a globally-unique name):

```bash
export RG="CapstoneSpring2026"
export WEBAPP="contoso-admin-portal-17079"  # change if taken

az webapp create \
  --resource-group "$RG" \
  --plan "asp-contoso-web-linux-b1" \
  --name "$WEBAPP" \
  --deployment-container-image-name "nginx:latest"
```

Sanity-check:

```bash
az webapp show \
  --name "$WEBAPP" \
  --resource-group "$RG" \
  --query "{name:name, state:state, host:defaultHostName}" \
  -o json
```

Also save the ACR login server:

```bash
export ACR_LOGIN_SERVER="$(az acr show -n contosoacr17079 --query loginServer -o tsv)"
echo "ACR_LOGIN_SERVER=$ACR_LOGIN_SERVER"
```

---

### 2) Build and push the image

From the `admin-portal/` directory:

```bash
cd admin-portal

export IMG_TAG="$(date +%Y%m%d-%H%M)"

az acr login -n contosoacr17079

docker build \
  -t "$ACR_LOGIN_SERVER/contoso-admin-portal:$IMG_TAG" \
  -t "$ACR_LOGIN_SERVER/contoso-admin-portal:latest" \
  .

docker push "$ACR_LOGIN_SERVER/contoso-admin-portal:$IMG_TAG"
docker push "$ACR_LOGIN_SERVER/contoso-admin-portal:latest"
```

---

### 3) Configure App Service to pull from ACR

#### Option A — Managed Identity (preferred)

This is the most secure approach. Requires permission to create role assignments on the ACR scope. If you get `AuthorizationFailed ... roleAssignments/write`, use Option B.

```bash
# Enable System-Assigned Managed Identity
az webapp identity assign --name "$WEBAPP" --resource-group "$RG"

# Get the identity and ACR resource IDs
export WEBAPP_PRINCIPAL_ID="$(az webapp identity show \
  --name "$WEBAPP" --resource-group "$RG" --query principalId -o tsv)"

export ACR_ID="$(az acr show -n contosoacr17079 --query id -o tsv)"

# Grant AcrPull
az role assignment create \
  --assignee-object-id "$WEBAPP_PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal \
  --role AcrPull \
  --scope "$ACR_ID"
```

Then point the web app at the image:

```bash
az webapp config container set \
  --name "$WEBAPP" \
  --resource-group "$RG" \
  --docker-custom-image-name "$ACR_LOGIN_SERVER/contoso-admin-portal:$IMG_TAG" \
  --docker-registry-server-url "https://$ACR_LOGIN_SERVER"
```

#### Option B — ACR Admin Credentials (works without RBAC writes)

```bash
az acr update -n contosoacr17079 --admin-enabled true

export ACR_USERNAME="$(az acr credential show -n contosoacr17079 --query username -o tsv)"
export ACR_PASSWORD="$(az acr credential show -n contosoacr17079 --query 'passwords[0].value' -o tsv)"

az webapp config container set \
  --name "$WEBAPP" \
  --resource-group "$RG" \
  --docker-custom-image-name "$ACR_LOGIN_SERVER/contoso-admin-portal:$IMG_TAG" \
  --docker-registry-server-url "https://$ACR_LOGIN_SERVER" \
  --docker-registry-server-user "$ACR_USERNAME" \
  --docker-registry-server-password "$ACR_PASSWORD"
```

---

### 4) Set App Settings (environment variables)

> ⚠️ **`WEBSITES_PORT=3000` is required.** Without it, Azure App Service routes external traffic to port 80, but the container listens on port 3000. This mismatch causes the "Application Error" screen even if the container itself is healthy.

Set all required variables at once:

```bash
az webapp config appsettings set \
  --name "$WEBAPP" \
  --resource-group "$RG" \
  --settings \
    WEBSITES_PORT=3000 \
    JWT_SECRET="<SET_A_LONG_RANDOM_STRING>" \
    PROJECT_ENDPOINT="https://test-agentusf1-resource.services.ai.azure.com/api/projects/Prod" \
    AGENT_NAME="AdminOrchestrator" \
    MCP_BASE_URL="https://seniorproject-mcp-container.azurewebsites.net/mcp"
```

**Optional variables** (set these if your setup uses them):

| Variable | Purpose |
| --- | --- |
| `MCP_API_KEY` | API key sent as `x-api-key` to the MCP service |
| `TOOL_API_BASE_URL` | Base URL for inventory tool API (SKU lookups) |
| `TOOL_API_KEY` | API key for the tool API |

After the initial setup, **manage environment variables through the Azure Portal**:
> App Service → Settings → Environment variables

Redeployments do not affect environment variables — they are stored in the App Service configuration, not in the container image.

#### Foundry authentication

The Admin Portal uses `DefaultAzureCredential` to call Azure AI Foundry. In App Service this resolves to the Managed Identity. Make sure:

1. The web app's Managed Identity is enabled (done in Step 3 Option A, or via Azure Portal → App Service → Identity → System assigned → On)
2. That identity has been granted the **`Azure AI User`** role on the Foundry resource (`test-agentusf1-resource`) — this must be done by a subscription owner or someone with role-assignment permissions

If the identity lacks access, `/admin/chat` will return a `401 Principal does not have access to API/Operation` error. See the [Foundry RBAC docs](https://aka.ms/FoundryPermissions) for full details on role assignments.

---

### 5) Verify the deployment

```bash
az webapp restart --name "$WEBAPP" --resource-group "$RG"

az webapp show --name "$WEBAPP" --resource-group "$RG" \
  --query defaultHostName -o tsv
```

Open `https://<defaultHostName>/` and log in with `admin` / `contoso123`.

Optional debug mode: `https://<defaultHostName>/dashboard.html?debug=1`

---

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| "Application Error" on every page | Container crashes on startup | Check logs: `az webapp log tail --name "$WEBAPP" --resource-group "$RG"` |
| "Application Error" but logs show app started | Port mismatch | Make sure `WEBSITES_PORT=3000` is set |
| `/admin/chat` returns 401 | Managed Identity lacks Foundry access | Ask a subscription owner to assign **Azure AI User** on `test-agentusf1-resource` to the App Service identity |
| Image not updated after redeploy | Azure reused cached layer | Use `redeploy.sh` — it updates the container config to the new tag, which forces a fresh pull |
| ACR pull fails (`unauthorized`) | Registry credentials not configured | Redo Step 3 — `redeploy.sh` sets credentials automatically via ACR admin |

To stream live container logs:

```bash
az webapp log tail --name "$WEBAPP" --resource-group "$RG"
```

---

## What does NOT require a redeploy

| Change | Action needed |
| --- | --- |
| MCP service redeployed (same URL) | None |
| Foundry agent instructions updated | None |
| Environment variable changed | Update in Azure Portal → App Service → Environment variables, then restart the web app |
| Admin Portal HTML/CSS/JS/server code changed | Run `./redeploy.sh` |
