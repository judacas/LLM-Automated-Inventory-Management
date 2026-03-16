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

Each agent definition should normally set its own `foundry.agent_name`. `AZURE_AI_AGENT_NAME` remains available as an optional fallback.

### 3. Install Dependencies

```bash
uv sync
```

### 4. Run The Server

```bash
uv run .
```

You can also point to a different agent definition directory:

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

Each `*_agent.toml` file controls the public A2A identity and the downstream Foundry agent:

```toml
[a2a]
name = "Your A2A Agent Name"
description = "What this agent does."
version = "1.0.0"
health_message = "Your A2A agent is running!"
default_input_modes = ["text"]
default_output_modes = ["text"]
streaming = true
# Optional. If omitted, the slug is derived from the filename.
slug = "your-agent"

[foundry]
agent_name = "Your-Foundry-Agent-Name"

[smoke_tests]
prompts = ["Prompt 1", "Prompt 2"]

[[skills]]
id = "primary_capability"
name = "Primary Capability"
description = "Describe the capability."
tags = ["tag1", "tag2"]
examples = ["Example 1", "Example 2"]
```

## Adding Another Agent

1. Copy `agents/agent.template.toml` to a new file such as `agents/inventory_agent.toml`.
2. Fill in the `a2a`, `foundry`, `skills`, and `smoke_tests` sections.
3. Start the server with `uv run .`.
4. Visit `http://localhost:10007/` to confirm the new agent was discovered.
5. Validate it with `uv run test_client.py --agent-slug inventory`.

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

## Architecture

- `__main__.py` loads all agent definitions from the configured directory and starts one multi-agent server.
- `app_factory.py` builds one A2A sub-app per agent and mounts it at `/<slug>`.
- `settings.py` generates the published per-agent URLs used in each agent card.
- `foundry_agent_executor.py` handles A2A requests and maps `context_id` values to Foundry conversations.
- `foundry_agent.py` talks to the portal-managed Foundry agent through the async SDK.
