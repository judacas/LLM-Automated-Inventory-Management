# Runbook

## What This Covers

This document explains how to run the A2A server locally, validate that it is healthy, expose it publicly for Foundry testing, and smoke test mounted agents.

## Prerequisites

- `uv` installed
- Python managed by `uv`
- access to an Azure AI Foundry project
- at least one Foundry agent already created in that project
- local Azure authentication that `DefaultAzureCredential` can use

Typical local auth options:

- `az login`
- Visual Studio Code Azure sign-in
- environment-based Azure credentials if your team uses those

## First-Time Setup

From the repository root:

```bash
uv sync
cd src/a2a_servers
cp .env.template .env
```

Edit `.env` and set at least:

```dotenv
AZURE_AI_PROJECT_ENDPOINT=https://<your-ai-services>.services.ai.azure.com/api/projects/<your-project>
A2A_AGENT_CONFIG_DIR=agents
A2A_HOST=localhost
A2A_PORT=10007
A2A_URL_MODE=local
LOG_LEVEL=INFO
```

Notes:

- `AZURE_AI_PROJECT_ENDPOINT` is required.
- `A2A_AGENT_CONFIG_DIR` defaults to `agents`, but setting it explicitly is clearer.
- If you use `A2A_URL_MODE=forwarded`, you must also set `A2A_FORWARDED_BASE_URL`.

## Confirm Agent Definitions

Before starting the server, verify that each discovered config points to a real Foundry agent.

Current examples:

- `agents/quote_agent.toml` -> Foundry agent name `quote-agent`
- `agents/math_agent.toml` -> Foundry agent name `Math-Agent`

If the name in TOML does not exist in the configured Foundry project, startup or first use will fail.

## Start The Server

From `src/a2a_servers`:

```bash
uv run .
```

Optional overrides:

```bash
uv run . --host 0.0.0.0 --port 10007
uv run . --agent-config-dir custom_agents
uv run . --url-mode forwarded --forwarded-base-url https://example.com
```

## What Healthy Startup Looks Like

On startup, the server should:

- load agent definitions
- log the public base URL
- log one block per mounted agent
- start listening on the configured host and port

Important endpoints to check:

- root index: `http://localhost:10007/`
- mounted agent health: `http://localhost:10007/<slug>/health`
- public agent card: `http://localhost:10007/<slug>/.well-known/agent-card.json`

## Smoke Test Locally

From `src/a2a_servers` in a second terminal:

```bash
uv run test_client.py
```

To target a single mounted agent:

```bash
uv run test_client.py --agent-slug quote
uv run test_client.py --agent-slug math
```

The test client will:

- call the mounted agent health endpoint
- fetch the public A2A agent card
- optionally fetch the extended card if advertised
- send one or more prompt-based requests
- print task status and final output

## Use With A Public URL

If Azure AI Foundry or another remote caller must reach your local machine, use a tunnel and publish proxy-aware URLs.

Required `.env` settings:

```dotenv
A2A_URL_MODE=forwarded
A2A_FORWARDED_BASE_URL=https://<public-host>
```

The mounted agent URLs will then be published as:

- `https://<public-host>/<slug>/`

## Dev Tunnel Flow

This package already assumes Azure Dev Tunnels is a supported development path.

Example flow:

```bash
devtunnel user login
devtunnel create my-a2a-agent -a
devtunnel port create -p 10007 --protocol http
devtunnel host my-a2a-agent
```

Then copy the printed HTTPS host into:

```dotenv
A2A_URL_MODE=forwarded
A2A_FORWARDED_BASE_URL=https://<your-tunnel-host>
```

Finally restart the A2A server so the published agent cards use the forwarded URL.

## Running With A Different Agent Set

You can point the runtime at a different folder of TOML definitions:

```bash
uv run . --agent-config-dir /absolute/path/to/agent-configs
```

This is useful when:

- testing experimental agents without changing the checked-in `agents/`
- running a reduced set of agents for a demo
- isolating one teammate's agent definitions from another's

## Operational Checks

When something seems wrong, check these in order:

1. `GET /` returns the expected list of agents and URLs.
2. `GET /<slug>/health` returns the configured health message.
3. `GET /<slug>/.well-known/agent-card.json` returns the expected public metadata.
4. the TOML `foundry.agent_name` matches a real Foundry agent.
5. `AZURE_AI_PROJECT_ENDPOINT` points to the correct Foundry project.
6. local Azure credentials are valid for that project.

## Shutdown Behavior

On process shutdown, the app lifespan handler calls executor cleanup, which attempts to:

- delete tracked Foundry conversations
- close the OpenAI client
- close the AI Projects client
- close Azure credentials

Because conversation tracking is in memory, a hard crash can leave Foundry conversations behind until they are cleaned up elsewhere.
