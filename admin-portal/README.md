# Contoso Admin Portal

**USF Capstone — Microsoft Project #1**

A Node.js / Express web application that gives Contoso administrators a protected dashboard and an AI-powered chat interface backed by an **Azure AI Foundry** agent.

---

## What it does

| Feature | Details |
|---|---|
| **Login / logout** | Hard-coded admin credentials, JWT cookie (HTTP-only, 1 h) |
| **Dashboard** | Live stat cards: outstanding quotes, total outstanding value, unavailable-but-requested items |
| **Admin Chat** | Full conversation with the Foundry agent; responses rendered as rich markdown (headings, tables, bold/italic, code, lists) |
| **Smooth scrolling** | Smart auto-scroll that respects manual scroll position |
| **MCP tool routing** | Separate `/admin/chat/tools` endpoint for keyword-dispatched tool calls (quotes, inventory, out-of-stock) |
| **Request tracing** | Every chat request carries a `requestId` logged server-side and shown in debug mode |

---

## Prerequisites

| Tool | Notes |
|---|---|
| Node.js 20+ | Required locally |
| Azure CLI (`az`) | Required for deployment |
| Docker Desktop | Required for building / pushing the container image |
| WSL (Windows) | Deployment script must run in WSL |
| An Azure account | With access to the shared `CapstoneSpring2026` resource group |

---

## Running locally

### 1. Install dependencies

```bash
cd admin-portal
npm install
```

### 2. Create `admin-portal/.env`

```ini
# Required — JWT signing key (any long random string)
JWT_SECRET=replace_me_with_a_long_random_string

# Required — Azure AI Foundry agent
PROJECT_ENDPOINT=https://test-agentusf1-resource.services.ai.azure.com/api/projects/test-agentusf1
AGENT_NAME=AdminOrchestrator

# Required — MCP service base URL (for dashboard metrics and tool endpoints)
MCP_BASE_URL=https://seniorproject-mcp-container.azurewebsites.net/mcp

# Optional — API keys if the MCP / tool API requires them
MCP_API_KEY=
TOOL_API_BASE_URL=
TOOL_API_KEY=
```

### 3. Authenticate to Azure

`DefaultAzureCredential` is used to call the Foundry agent. Locally this resolves to your Azure CLI session:

```bash
az login
```

Your signed-in identity must have the **Azure AI User** role on the Foundry resource (`test-agentusf1-resource`). Ask a subscription owner to assign it if you see a `401` when using the chat.

### 4. Start the server

```bash
npm start
```

Open `http://localhost:3000` and log in with:

- **Username:** `admin`
- **Password:** `contoso123`

---

## Deployment

The app is deployed as a Linux container on **Azure App Service**, pulling from **Azure Container Registry (ACR)**.

Full first-time setup and troubleshooting steps are in:

> [`docs/deploy-acr-appservice.md`](docs/deploy-acr-appservice.md)

### Redeploying after a code change

```bash
# From the admin-portal/ directory in WSL:
./redeploy.sh
```

`redeploy.sh` builds a new image, pushes it to ACR with a timestamp tag, and updates the App Service container config so Azure pulls the new image immediately.

**Environment variables are managed in the Azure Portal** (App Service → Settings → Environment variables) and are never touched by the script.

---

## Key endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/auth/login` | — | Issue JWT cookie |
| `POST` | `/auth/logout` | — | Clear cookies |
| `GET` | `/dashboard.html` | ✔ | Protected dashboard page |
| `GET` | `/admin/dashboard` | ✔ | Live stat cards (calls MCP) |
| `POST` | `/admin/chat` | ✔ | Foundry agent conversation |
| `POST` | `/admin/chat/tools` | ✔ | Keyword-dispatched MCP tool calls |

---

## Debugging

### UI debug mode

Add `?debug=1` to the dashboard URL:

```
http://localhost:3000/dashboard.html?debug=1
https://<app-service-hostname>/dashboard.html?debug=1
```

When active, a **🐛 Debug** panel opens below the chat box showing:

| Section | What it shows |
|---|---|
| **Runtime** | Node.js version, platform, PID, server uptime, RSS and heap memory |
| **Environment** | Status of every required env var (✓ set / ✗ MISSING / — not set) |
| **Event log** | Color-coded rolling log of every client and server event |

**Log entry colors:**

| Color | Level | When |
|---|---|---|
| Blue | INFO | Request sent, system info loaded |
| Green | SUCCESS | Dashboard loaded, chat response received OK |
| Yellow | WARN | Empty agent response, non-2xx from server |
| Red | ERROR | Network failure, missing modules, request timeout |

Each successful chat response also shows: `durationMs`, `conversationId`, `newConversation`, `replyChars`, and `outputTypes` from the Foundry response — all pulled live from the server.

**Toolbar buttons:** Copy log (copies all entries as JSON to clipboard) · Clear (resets the log).

### Server logs

On startup the server logs its full configuration status — useful for verifying env vars are set correctly in both local and deployed environments:

```
[startup] Node.js v20.x | PID 12345 | PORT 3000
[startup] Config: JWT_SECRET=SET | PROJECT_ENDPOINT=https://... | AGENT_NAME=AdminOrchestrator | ...
```

Logs are written to `logs/server.log` (local) and to the App Service log stream (deployed).

Stream live logs from Azure:

```bash
az webapp log tail --name "<WEBAPP>" --resource-group "CapstoneSpring2026"
```

Search for a specific request by ID:

```
[<requestId>] Admin chat from admin: ...
[<requestId>] Admin chat success (1234ms, chars=456)
[<requestId>] [DEBUG] conversationId=conv_abc newConversation=false outputTypes=["message"]
[<requestId>] Admin chat error (67ms): ...
```

### Debug info API

`GET /admin/debug/info` (auth required) returns a JSON snapshot of the server's current state — the same data shown in the UI debug panel:

```json
{
  "node": "v20.11.0",
  "platform": "linux/x64",
  "pid": 12345,
  "uptimeSec": 3600,
  "memory": { "rss": "85.2 MB", "heapUsed": "42.1 MB", "heapTotal": "60.0 MB" },
  "env": {
    "JWT_SECRET": "✓ set",
    "PROJECT_ENDPOINT": "https://...",
    "AGENT_NAME": "AdminOrchestrator",
    "MCP_BASE_URL": "https://...",
    "MCP_API_KEY": "✓ set"
  },
  "timestamp": "2026-03-25T19:00:00.000Z"
}
```

### MCP tool approvals

Some prompts trigger MCP tool calls that require manual approval in the Foundry portal. When this happens, `POST /admin/chat` returns HTTP `409`:

```
MCP tool call requires approval in Foundry portal. Pending approval request(s): mcpr_...
```

Approve the request in the [Foundry portal](https://ai.azure.com), then retry the prompt.

---

## Project structure

```
admin-portal/
├── docs/
│   └── deploy-acr-appservice.md   # Full deployment guide
├── public/
│   ├── index.html                 # Login page
│   ├── dashboard.html             # Dashboard + chat UI
│   └── style.css                  # All styles
├── utils/
│   ├── foundryClient.js           # Azure AI Foundry conversation client
│   └── logger.js                  # Winston logger
├── server.js                      # Express app + all routes
├── Dockerfile                     # Container image definition
├── redeploy.sh                    # One-command redeploy script (WSL)
├── package.json
└── .env                           # Local only — never committed
```

---

## Known limitations

- Admin credentials (`admin` / `contoso123`) are hard-coded. This is intentional for the capstone prototype.
- The **View All Quotes** and **View Inventory** nav buttons on the dashboard are UI placeholders — no pages are wired behind them yet.
- The Foundry agent requires an admin to grant the **Azure AI User** role to the App Service Managed Identity before the deployed chat will work (see `docs/deploy-acr-appservice.md` § Foundry authentication).
