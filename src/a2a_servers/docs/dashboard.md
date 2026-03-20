# A2A Agent Dashboard

A simple developer-facing dashboard for viewing, adding, editing, and removing
A2A agent configurations without touching the file system by hand.

---

## Running the dashboard

The dashboard is built into the A2A server. Start the server normally:

```bash
cd src/a2a_servers
uv run python -m a2a_servers
```

Then open your browser at:

```
http://localhost:10007/dashboard/
```

The dashboard is available whenever the server is running. No extra process
or build step is needed.

---

## How it works

### Agent definitions

Agents are defined as TOML files in the `agents/` directory (or in the directory
specified by `--agent-config-dir` / `A2A_AGENT_CONFIG_DIR`).
Each file must match the glob `*_agent.toml` and contain `[a2a]`, `[foundry]`,
and at least one `[[skills]]` section. See `agents/agent.template.toml` for the
full schema.

### Dashboard layout

| Section | URL | Description |
|---------|-----|-------------|
| UI | `GET /dashboard/` | The browser dashboard page |
| List agents | `GET /dashboard/api/agents` | JSON list of all configured agents |
| Get one agent | `GET /dashboard/api/agents/{slug}` | JSON for a single agent |
| Create agent | `POST /dashboard/api/agents` | Write a new `*_agent.toml` file |
| Edit agent | `PUT /dashboard/api/agents/{slug}` | Overwrite an existing TOML file |
| Delete agent | `DELETE /dashboard/api/agents/{slug}` | Remove the TOML file |
| Reload | `POST /dashboard/api/reload` | Re-read all TOMLs and hot-swap the router |

### Adding an agent

1. Click **+ New Agent** in the dashboard.
2. Fill in the filename (must end with `_agent.toml` to be auto-discovered), the
   A2A fields, the Foundry agent name, and at least one skill.
3. Click **Create Agent**.

The new TOML file is validated using the same parser that the server uses at
startup. Invalid configs are rejected with a clear error message before anything
is written to disk.

### Editing an agent

1. Click an agent in the sidebar.
2. Update the fields.
3. Click **Save**.

Validation runs again before the file is overwritten.

### Removing an agent

1. Click the agent in the sidebar.
2. Click **Delete** and confirm.

The `.toml` file is deleted immediately. Use **Reload Agents** to update the
live routing table.

### Reload / hot-swap

Click **⟳ Reload Agents** (or `POST /dashboard/api/reload`) to:

1. Re-read and validate all TOML files in the agents directory.
2. If `AZURE_AI_PROJECT_ENDPOINT` is configured, rebuild the live Starlette
   routing table and swap it in-place — no server restart required.
3. If `AZURE_AI_PROJECT_ENDPOINT` is not set (e.g. a local dev machine without
   Azure credentials), validation still runs but routing is not updated. Restart
   the server to apply config changes in that case.

> **Note:** Azure Foundry backend connections are lazy — they are established
> on the first actual A2A request, not on startup or reload. Reloading is safe
> even if Azure is unreachable at the time of the reload.

> **Note:** When a hot-swap happens, any in-flight requests to an agent being
> replaced may fail. For a developer tool this is acceptable; the dashboard is
> not intended for production use.

---

## Dashboard code layout

```
src/a2a_servers/
├── dashboard/
│   ├── __init__.py       # package marker
│   ├── api.py            # Starlette route handlers for the CRUD + reload API
│   ├── toml_writer.py    # Serialise config dicts back to TOML text
│   └── ui.py             # Embedded single-file HTML dashboard (no build step)
├── app_factory.py        # SwappableAgentApp + create_app (dashboard mounted here)
└── docs/
    └── dashboard.md      # This file
```

### Key design choices

- **No extra dependencies** — TOML writing is done with a small hand-rolled
  serialiser (`toml_writer.py`) rather than adding a library.
- **No build step** — the entire UI is a single HTML string embedded in
  `ui.py`, served directly by Starlette.
- **Hot-swap via `SwappableAgentApp`** — a thin ASGI wrapper whose inner
  `Starlette` app can be replaced atomically while the outer server
  (lifespan, dashboard routes) keeps running.
- **Validation before write** — every `POST` and `PUT` validates the config
  by writing it to a temp file and running `load_agent_definition` before
  touching the real file.
