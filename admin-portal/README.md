## Admin Portal (USF Capstone – Microsoft Project #1)

This folder contains the **Contoso Admin Portal** (Node.js + Express + static HTML/CSS/JS).

It currently supports:

- Admin login (temporary hard-coded credentials)
- A protected dashboard page (`/dashboard.html`)
- An Admin Chat UI backed by an **Azure AI Foundry** agent (via `@azure/ai-projects` + `DefaultAzureCredential`)
- Lightweight tracing + log correlation for the chat flow

---

## What Works Now

### 1) Auth + basic portal

- `POST /auth/login` issues a JWT (cookie, HTTP-only, 1 hour)
- `POST /auth/logout` clears auth + chat conversation cookie
- `GET /dashboard.html` is protected (requires the auth cookie)

**Default credentials (temporary):**

- Username: `admin`
- Password: `contoso123`

### 2) Admin Chat (Foundry agent)

- Chat UI lives in `public/dashboard.html`.
- The UI shows a **Thinking / Loading** placeholder while waiting.
- Responses are rendered using a safe “markdown-lite” formatter:
    - headings (`#`, `##`, `###`)
    - bold (`**text**`)
    - inline code (`` `code` ``)
    - fenced code blocks (```...```)
    - bullet/numbered lists (including nested indentation)
    - key/value formatting (`Label: value`) and quote-style sections

### 3) Debugging + tracing (request correlation)

- UI debug mode: open `http://localhost:3000/dashboard.html?debug=1`
    - Shows a Debug panel with a rolling log of chat request/response events.
    - Displays a `requestId` next to the agent label for correlation.

- Every `/admin/chat` request includes an `x-request-id` header (generated in the browser).
- The server logs the same ID and returns it in the JSON response.

### 4) Dashboard stats (data-source dependent)

The dashboard calls `GET /admin/dashboard`, which **currently expects** an external service to provide metrics.

- If the upstream API is available and configured, the dashboard will show:
    - Outstanding Quotes
    - Outstanding Total (currency string)
    - Unavailable Items Requested
- If the upstream API is missing/unreachable, the server falls back to `0` values.

---

## What Still Needs Work

- UI polish (spacing/visual tweaks). Functionality is in good shape.
- Dashboard “summary” is not truly complete until it has a reliable data source.
    - Right now `GET /admin/dashboard` relies on upstream endpoints (see **Environment variables** below).
    - If MCP cannot provide the metrics in your environment, you’ll need a real API (or a different backend integration) to supply those values.
- The “View All Quotes” / “View Inventory” buttons are currently UI placeholders (no navigation wired).

---

## Running Locally

From the repo root:

1) Install dependencies

```bash
cd admin-portal
npm install
```

2) Create `admin-portal/.env`

Minimum required:

```ini
# Required for JWT signing
JWT_SECRET=replace_me_with_a_long_random_string

# Required for Admin Chat (Azure AI Foundry)
PROJECT_ENDPOINT=https://<your-foundry-project-endpoint>
AGENT_NAME=<your-agent-name>

# Required for dashboard metrics + tool-style commands (if used)
MCP_BASE_URL=http://localhost:<port>
```

Optional:

```ini
MCP_API_KEY=

# Optional: only used by /admin/chat/tools for SKU lookups
TOOL_API_BASE_URL=http://localhost:<port>
TOOL_API_KEY=
```

3) Ensure `DefaultAzureCredential` can authenticate

- Local dev typically uses Azure CLI auth (example):

```bash
az login
```

Your signed-in identity must have access to the Foundry project/agent.

4) Start the server

```bash
npm start
```

5) Open:

- `http://localhost:3000`

---

## Key Endpoints

- `POST /auth/login` (body: `{ "username": "admin", "password": "..." }`)
- `POST /auth/logout`
- `GET /dashboard.html` (protected)
- `GET /admin/dashboard` (protected; calls upstream metrics endpoints)
- `POST /admin/chat` (protected; calls Foundry agent)
- `POST /admin/chat/tools` (protected; optional “tool-style” routing to upstream APIs)

---

## Chat Debugging (Complete Notes)

### UI debug mode

Open the dashboard with:

- `http://localhost:3000/dashboard.html?debug=1`

When enabled:

- The chat UI shows a **Debug** panel with a rolling log of request/response events.
- Each agent response shows a `requestId` for correlation.

### Server logs

Logs are written to:

- `admin-portal/logs/server.log`

Search for the request ID shown in the UI:

- `[<requestId>] Admin chat ...`
- `[<requestId>] Admin chat success ...`
- `[<requestId>] Admin chat error ...`

### “Empty response” vs “Failure”

- **Empty agent response**: request succeeded but no text was extractable from the Foundry response.
    - Server returns `{ success: true, empty: true }`.
- **Failure**: request failed due to network/server/Foundry errors.
    - Server returns `{ success: false }` and an HTTP 4xx/5xx.

If you see frequent **empty** responses, it usually indicates the text extraction logic needs to be updated to match the current Foundry response schema.

---

## MCP Tool Approvals (Manual)

Some prompts trigger MCP tool calls that require explicit approval.

- This project intentionally does **not** auto-approve MCP tool calls.
- If approval is required, `POST /admin/chat` returns HTTP `409` and an error like:
    - `MCP tool call requires approval in Foundry portal. Pending approval request(s): mcpr_...`

Approve the request in the Foundry portal, then retry the same prompt in the Admin Chat UI.

---

## Notes / Caveats

- This is a capstone prototype:
    - Admin credentials are hard-coded.
    - JWT secret must be provided in `.env`.
- `node_modules/` and `logs/` should remain ignored by git.