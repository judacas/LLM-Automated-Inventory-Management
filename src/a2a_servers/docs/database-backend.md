# Database-Backed Agent Definitions

This document explains how agent definitions can be stored in and loaded from
Azure Table Storage instead of local TOML files.

## Why Azure Table Storage?

Azure Table Storage is the simplest Azure-native key-value store:

- No server to provision — it is part of every Azure Storage Account.
- Flat row structure matches the agent definition schema well.
- Supports both connection-string auth (dev) and managed identity (prod).
- The `azure-data-tables` SDK is lightweight and maintained by Microsoft.
- Scales to thousands of agent records without configuration.

## Database Schema

All agents are stored in a single Azure Storage table (default name:
`a2aagents`). Each row represents one agent.

| Column | Type | Description |
|---|---|---|
| `PartitionKey` | string | Always `"agents"` |
| `RowKey` | string | Agent slug (unique identifier, e.g. `"math"`) |
| `public_name` | string | Human-readable display name |
| `description` | string | What the agent does |
| `version` | string | Semantic version string |
| `health_message` | string | Text returned by `/health` |
| `foundry_agent_name` | string | Name of the Azure AI Foundry agent to call |
| `default_input_modes_json` | string (JSON) | e.g. `["text"]` |
| `default_output_modes_json` | string (JSON) | e.g. `["text"]` |
| `skills_json` | string (JSON) | Array of skill objects (see below) |
| `smoke_test_prompts_json` | string (JSON) | Array of test prompt strings |
| `supports_streaming` | bool | Whether streaming is enabled |

### Skill object shape (inside `skills_json`)

```json
{
  "id": "math_computation",
  "name": "Math Computation",
  "description": "Solve math problems.",
  "tags": ["math", "code-interpreter"],
  "examples": ["What is 2 + 2?"]
}
```

List-typed fields (`default_input_modes_json`, `default_output_modes_json`,
`skills_json`, `smoke_test_prompts_json`) are stored as JSON strings because
Azure Table Storage only supports flat scalar properties.

## Configuration

Copy `.env.template` to `.env` and set **one** of the following:

| Environment variable | Purpose |
|---|---|
| `AZURE_STORAGE_CONNECTION_STRING` | Full connection string — easiest for local dev and CI |
| `AZURE_STORAGE_ACCOUNT_URL` | Account URL (e.g. `https://<account>.table.core.windows.net`); uses `DefaultAzureCredential` — recommended for Azure production with managed identity |
| `A2A_AGENTS_TABLE` | Name of the Storage table (default: `a2aagents`) |

When neither storage variable is set the server falls back to loading agent
definitions from local TOML files (original behaviour, unchanged).

## Seeding the Database from TOML Files

Run the `seed-db` subcommand once to migrate your existing agent TOML files
into the table. It will create the table if it does not exist and upsert every
`*_agent.toml` found in the agent config directory.

```bash
# Using a connection string (local dev / Azurite emulator):
python -m a2a_servers seed-db \
  --connection-string "UseDevelopmentStorage=true" \
  --agent-config-dir src/a2a_servers/agents

# Using managed identity on Azure (recommended for production):
python -m a2a_servers seed-db \
  --account-url "https://<account>.table.core.windows.net" \
  --agent-config-dir src/a2a_servers/agents

# All options can also be supplied via env vars:
AZURE_STORAGE_CONNECTION_STRING="..." \
python -m a2a_servers seed-db
```

Re-running `seed-db` is safe: existing records are replaced (upserted), so
the table always reflects the current TOML files after each run.

## Starting the Server with DB-backed Loading

```bash
AZURE_STORAGE_CONNECTION_STRING="..." \
AZURE_AI_PROJECT_ENDPOINT="https://..." \
python -m a2a_servers serve
```

Or with managed identity on Azure:

```bash
AZURE_STORAGE_ACCOUNT_URL="https://<account>.table.core.windows.net" \
AZURE_AI_PROJECT_ENDPOINT="https://..." \
python -m a2a_servers serve
```

When either storage variable is set the server loads all rows from the
`PartitionKey = "agents"` partition and validates them before mounting any
routes. An invalid or incomplete row causes a clear error at startup — the
server will not partially start.

## Local Development with the Azurite Emulator

[Azurite](https://github.com/Azure/Azurite) is the official local emulator for
Azure Storage.

```bash
# Install and start Azurite (requires Node.js):
npx azurite --silent --location /tmp/azurite

# Seed and run with the emulator:
AZURE_STORAGE_CONNECTION_STRING="UseDevelopmentStorage=true" \
AZURE_AI_PROJECT_ENDPOINT="https://..." \
python -m a2a_servers seed-db

AZURE_STORAGE_CONNECTION_STRING="UseDevelopmentStorage=true" \
AZURE_AI_PROJECT_ENDPOINT="https://..." \
python -m a2a_servers serve
```

## How Agent Loading Works

1. `__main__.py` calls `load_server_settings()` which reads the storage env vars.
2. If `settings.use_db` is `True` (at least one storage var is set),
   `load_agent_definitions_from_db()` is called.
3. That function queries `PartitionKey eq 'agents'` in the configured table.
4. Each entity is deserialised by `_definition_from_entity()` into an
   `AgentDefinition` object. JSON fields are parsed and every required field is
   validated; missing or malformed records raise a `ValueError` that prevents
   startup.
5. Duplicate slug or Foundry agent name checks are run across all loaded records.
6. The resulting `tuple[AgentDefinition, ...]` is passed to `create_app()` — the
   same function used by the file-based path — so all downstream behaviour
   (routing, health checks, A2A agent cards) is identical.

## Fallback to File-Based Loading

If neither `AZURE_STORAGE_CONNECTION_STRING` nor `AZURE_STORAGE_ACCOUNT_URL` is
set, the server behaves exactly as before: it discovers `*_agent.toml` files
from the directory configured by `A2A_AGENT_CONFIG_DIR` (or the bundled
`agents/` directory by default). No code change is needed to go back to
file-based loading.
