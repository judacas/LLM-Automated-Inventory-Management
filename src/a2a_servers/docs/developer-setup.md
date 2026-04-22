# Developer Setup

## Purpose

This document is the developer onboarding guide for `src/a2a_servers`.

It covers environment setup only.

For task-specific guides, use:

- add a new agent: [adding-agents.md](./adding-agents.md)
- redeploy after a change: [redeploying.md](./redeploying.md)
- local public testing with Dev Tunnels: [local-testing-with-devtunnels.md](./local-testing-with-devtunnels.md)
- local run and smoke-test checks: [runbook.md](./runbook.md)

## Tooling

- `uv` for environment and dependency management
- Python version compatible with `src/a2a_servers/pyproject.toml`

> **Note:** Ensure you have Azure authentication configured. If you haven't already set up Azure CLI authentication, run `az login` in your terminal. For more information on Azure authentication methods, refer to the [Azure CLI authentication documentation](https://learn.microsoft.com/en-us/cli/azure/authenticate-azure-cli?view=azure-cli-latest).

- Azure authentication available to `DefaultAzureCredential`

From the repository root:

```bash
uv sync
```

Then work from:

```bash
cd src/a2a_servers
```

## Local Environment File

Create a local env file:

```bash
cp .env.template .env
```

Minimum required value:

```dotenv
AZURE_AI_PROJECT_ENDPOINT=https://<your-ai-services>.services.ai.azure.com/api/projects/<your-project>
```

Recommended development values:

```dotenv
A2A_AGENT_CONFIG_DIR=agents
A2A_HOST=localhost
A2A_PORT=10007
A2A_URL_MODE=local
LOG_LEVEL=INFO
```

## Running Tests

From `src/a2a_servers`:

```bash
uv run pytest tests
```

If you prefer running from the repository root, pass the package project explicitly so pytest uses `src/a2a_servers/pyproject.toml` settings:

```bash
uv run --project src/a2a_servers pytest src/a2a_servers/tests
```

## Running The Server

From `src/a2a_servers`:

```bash
uv run python __main__.py
```

Useful variants:

```bash
uv run python __main__.py --agent-config-dir custom_agents
uv run python __main__.py --url-mode forwarded --forwarded-base-url https://example.com
```

## Running Smoke Tests

From `src/a2a_servers`:

```bash
uv run python test_client.py
uv run python test_client.py --agent-slug quote
```

For the full local validation flow, see [runbook.md](./runbook.md).

## Common Development Tasks

### Lint

From the repository root:

```bash
uv run ruff check src/a2a_servers
```

### Type Check

From the repository root:

```bash
uv run mypy src
```

### Run A Single Test File

```bash
uv run pytest src/a2a_servers/tests/test_agent_definition.py
```

## Working Conventions

- keep agent names in TOML aligned with real Foundry agent names
- add smoke-test prompts whenever behavior changes
- use realistic skills metadata because other agents may rely on the published agent card
- do not assume the current examples represent the final project architecture; they are scaffolding plus integration glue

## Files Worth Reading First

- [README.md](../README.md)
- [docs/architecture.md](./architecture.md)
- [docs/adding-agents.md](./adding-agents.md)
- [agent_definition.py](../agent_definition.py)
- [app_factory.py](../app_factory.py)
- [foundry_agent_executor.py](../foundry_agent_executor.py)
