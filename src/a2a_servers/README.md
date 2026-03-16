# Config-Driven Foundry A2A Server

This project runs one A2A server process that discovers multiple agent definitions from the `agents/` directory. Each TOML file becomes its own mounted A2A endpoint, while the runtime, networking, and Azure AI Foundry integration stay shared.

## Project Structure

```text
├── agents/
│   ├── agent.template.toml    # Starter template for new agents
│   ├── math_agent.toml        # Example math agent definition
│   └── quote_agent.toml       # Example quote agent definition
├── agent_definition.py        # Loads and validates agent definitions
├── settings.py                # Host, port, URL mode, and URL generation
├── app_factory.py             # Builds the multi-agent Starlette + A2A app
├── foundry_agent.py           # Reusable Azure AI Foundry backend
├── foundry_agent_executor.py  # Generic A2A executor for a Foundry backend
├── __main__.py                # Thin CLI entrypoint
├── test_client.py             # Smoke test client for one or many agents
└── .env.template              # Environment variables template
```

## Quick Start

### 1. Prerequisites

- Python 3.12+
- An Azure AI Foundry project with deployed backend agents
- `az login` completed for `DefaultAzureCredential`

### 2. Environment Setup

```bash
cp .env.template .env
```

Set at least:

- `AZURE_AI_PROJECT_ENDPOINT`
- `A2A_AGENT_CONFIG_DIR=agents`
- Each agent definition must set its own `foundry.agent_name`

### 3. Install Dependencies

```bash
uv sync
```

### 4. Run The Server

```bash
uv run .
```

You can also point to a different agent definition directory (optional):

```bash
uv run . --agent-config-dir custom_agents
```

### 5. Run Smoke Tests

Test all discovered agents:

```bash
uv run test_client.py
```

Test a single agent by slug:

```bash
uv run test_client.py --agent-slug quote
```

## Agent Discovery

The server discovers every file matching `agents/*_agent.toml`.

- `math_agent.toml` becomes slug `math`
- `quote_agent.toml` becomes slug `quote`
- You can override the derived slug with `a2a.slug`

Startup fails if two definitions resolve to the same slug or the same Foundry backend agent name.

## URL Model

Each agent is mounted under its own path prefix:

- local: `http://localhost:10007/<slug>/`
- dev tunnel: `https://your-tunnel-host/<slug>/`
- App Service: `https://your-app-host/<slug>/`

With the example configs, the endpoints are:

- `http://localhost:10007/math/`
- `http://localhost:10007/quote/`

Each mounted agent keeps the SDK-provided A2A routes under that prefix:

- `POST /<slug>/`
- `GET /<slug>/.well-known/agent-card.json`
- `GET /<slug>/.well-known/agent.json`
- `GET /<slug>/agent/authenticatedExtendedCard` when applicable
- `GET /<slug>/health`

The root `/` endpoint returns a small index of the loaded agents and their published URLs.

## Agent Definition Format

Each `*_agent.toml` file defines an agent's public A2A identity and its downstream Foundry agent. Use [`agents/agent.template.toml`](agents/agent.template.toml) as a starting point. To add or configure an agent:

1. Copy the template to a new file (e.g., `agents/inventory_agent.toml`):

    ```bash
    cp agents/agent.template.toml agents/<your_agent_name>_agent.toml
    ```

2. Edit your new file to fill in the `a2a`, `foundry`, `skills`, and `smoke_tests` sections to suit your agent.
3. Start the server with `uv run .`.
4. Visit `http://localhost:10007/` to confirm the agent appears in the list.
5. Validate the agent with:

    ```bash
    uv run test_client.py --agent-slug <agent_slug>
    ```

Replace `<your_agent_name>` and `<agent_slug>` as appropriate.

## URL Modes

The server always binds locally on `A2A_HOST:A2A_PORT`. `A2A_URL_MODE` controls what base host is published in each agent card:

- `local`: advertises `http://[host]:[port]/<slug>/`
- `forwarded`: advertises `A2A_FORWARDED_BASE_URL/<slug>/`

Example:

```bash
A2A_URL_MODE=forwarded
A2A_FORWARDED_BASE_URL=https://your-public-url.example
```

This is useful when the server is exposed through a tunnel or reverse proxy for testing.

### Using Azure Dev Tunnels

Until this service is deployed, Azure AI Foundry needs a public URL that can reach your local A2A server. Azure Dev Tunnels is the easiest way to provide that.

#### One-time setup (create a persistent tunnel)

This creates a **persistent** tunnel you can reuse. You do **not** need to create it every time.

1. Install the `devtunnel` CLI if you do not already have it.
2. Sign in:

   ```bash
   devtunnel user login
   ```

3. Create a tunnel with a reusable ID and allow anonymous access.

   > The `TUNNEL_ID=...` line below is just a Bash convenience; if you prefer, you can skip it and replace `"$TUNNEL_ID"` with a literal value like `my-a2a-agent` in the commands.

   ```bash
   TUNNEL_ID=my-a2a-agent
   devtunnel create "$TUNNEL_ID" -a
   ```

   Using an explicit tunnel ID makes it easier to find and reuse the same tunnel later, especially if you already have other dev tunnels.

4. Add the local A2A server port to the tunnel:

   ```bash
   devtunnel port create -p 10007 --protocol http
   ```

   > `10007` is only the default from `.env.template`. If your `.env` uses a different `A2A_PORT`, use that port instead.

#### Run (start server + host the tunnel)

Both the server and the tunnel host run in the foreground, so you’ll want **two terminals**: one for `uv run .` and one for `devtunnel host ...`.

1. In the first terminal, host the tunnel:

   ```bash
   devtunnel host "$TUNNEL_ID"
   ```

2. Copy the public HTTPS URL that `devtunnel host` prints for the port you exposed, then set (or confirm) these values in your `.env`:

   ```bash
   A2A_URL_MODE=forwarded
   A2A_FORWARDED_BASE_URL=https://<your-tunnel-url>
   ```

For example, if Dev Tunnels prints `https://abc123-10007.use2.devtunnels.ms/`, set `A2A_FORWARDED_BASE_URL` to that base URL. The agent card will then publish `https://abc123-10007.use2.devtunnels.ms/<slug>/`.

You normally only need to update `A2A_FORWARDED_BASE_URL` the **first time** you create and host this persistent tunnel. As long as you reuse the same tunnel ID and Dev Tunnels gives you the same URL, you don’t need to restart the server just to change it.

3. In a **second** terminal, start the local server so it picks up the latest `.env` values:

   ```bash
   uv run .
   ```

If you need to come back to the same tunnel later, you can host it again with `devtunnel host "$TUNNEL_ID"` instead of relying on whichever tunnel was used most recently.

## Architecture

- `__main__.py` loads all agent definitions from the configured directory and starts one multi-agent server.
- `app_factory.py` builds one A2A sub-app per agent and mounts it at `/<slug>`.
- `settings.py` generates the published per-agent URLs used in each agent card.
- `foundry_agent_executor.py` handles A2A requests and maps `context_id` values to Foundry conversations.
- `foundry_agent.py` talks to the portal-managed Foundry agent through the async SDK.
