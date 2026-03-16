# Config-Driven Foundry A2A Server

This project runs one A2A server process per agent, but the server is now driven by an `agent.toml` definition instead of hardcoded math metadata in `__main__.py`. The goal is to let teammates create another server-backed agent by editing config, not by learning the runtime internals.

## What Changed

- The reusable server runtime is now generic.
- A2A-visible identity, skills, health text, and smoke-test prompts live in `agent.toml`.
- The Foundry backend agent name can be declared in `agent.toml`.
- The current math agent is just the default definition shipped in this folder.

## Project Structure

```text
├── agent.toml                # Current math agent definition
├── agent.template.toml       # Starter template for teammates
├── agent_definition.py       # Loads and validates agent.toml
├── settings.py               # Host, port, URL mode, and endpoint settings
├── app_factory.py            # Builds the Starlette + A2A app
├── foundry_agent.py          # Reusable Azure AI Foundry backend
├── foundry_agent_executor.py # Generic A2A executor for a Foundry backend
├── __main__.py               # Thin CLI entrypoint
├── test_client.py            # Smoke test client driven by agent.toml
└── .env.template             # Environment variables template
```

## Quick Start

### 1. Prerequisites

- Python 3.12+
- An Azure AI Foundry project with a deployed agent
- `az login` completed for `DefaultAzureCredential`

### 2. Environment Setup

```bash
cp .env.template .env
```

Set at least:

- `AZURE_AI_PROJECT_ENDPOINT`
- `A2A_AGENT_DEFINITION=agent.toml`

`foundry.agent_name` can live in `agent.toml`. `AZURE_AI_AGENT_NAME` remains available as a compatibility fallback.

### 3. Install Dependencies

```bash
uv sync
```

### 4. Run The Server

```bash
uv run .
```

You can also point to a different agent definition file:

```bash
uv run . --agent-config my_agent.toml
```

### 5. Run The Smoke Test

```bash
uv run test_client.py
```

The smoke test reads prompts from the active agent definition, so each teammate can keep their own realistic checks close to their agent metadata.

## Agent Definition Format

The `agent.toml` file controls the public A2A identity and the downstream Foundry agent:

```toml
[a2a]
name = "Your A2A Agent Name"
description = "What this agent does."
version = "1.0.0"
health_message = "Your A2A agent is running!"
default_input_modes = ["text"]
default_output_modes = ["text"]
streaming = true

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

## Teammate Onboarding

To create another single-agent server:

1. Copy `agent.template.toml` to a new file such as `sales_agent.toml`.
2. Fill in the `a2a`, `foundry`, `skills`, and `smoke_tests` sections.
3. Set `A2A_AGENT_DEFINITION=sales_agent.toml` in `.env`, or run `uv run . --agent-config sales_agent.toml`.
4. Start the server with `uv run .`.
5. Validate it with `uv run test_client.py`.

This keeps the deployment model simple: one process, one A2A agent, one Foundry agent behind it.

## URL Modes

The server always binds locally on `A2A_HOST:A2A_PORT`. `A2A_URL_MODE` controls what URL is published in the agent card:

- `local`: advertises `http://[host]:[port]/`
- `forwarded`: advertises `A2A_FORWARDED_BASE_URL`

Example:

```bash
A2A_URL_MODE=forwarded
A2A_FORWARDED_BASE_URL=https://your-public-url.example
```

This is useful when the server is exposed through a tunnel or reverse proxy for testing.

## Architecture

- `__main__.py` loads settings and the selected `agent.toml`, then starts the app.
- `app_factory.py` builds the `AgentCard`, request handler, health route, and shutdown cleanup.
- `foundry_agent_executor.py` handles A2A requests and maps `context_id` values to Foundry conversations.
- `foundry_agent.py` talks to the portal-managed Foundry agent through the async SDK.

## Current Default Agent

The checked-in `agent.toml` still describes the existing math agent, so current behavior is preserved while making the runtime reusable for future agents.
