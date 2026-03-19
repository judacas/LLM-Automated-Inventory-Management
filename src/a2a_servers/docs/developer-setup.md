# Developer Setup

## Purpose

This document is the developer onboarding guide for `src/a2a_servers`.

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

If you need a public tunnel:

```dotenv
A2A_URL_MODE=forwarded
A2A_FORWARDED_BASE_URL=https://<your-public-host>
```

## Running Tests

From the repository root:

```bash
uv run pytest src/a2a_servers/tests
```

From `src/a2a_servers`:

```bash
uv run pytest tests
```

## Running The Server

From `src/a2a_servers`:

```bash
uv run .
```

Useful variants:

```bash
uv run . --agent-config-dir custom_agents
uv run . --url-mode forwarded --forwarded-base-url https://example.com
```

## Running Smoke Tests

From `src/a2a_servers`:

```bash
uv run test_client.py
uv run test_client.py --agent-slug quote
```

## Adding A New Agent

1. Copy the template:

   ```bash
   cp agents/agent.template.toml agents/<name>_agent.toml
   ```

2. Update:

   - `[a2a]`
   - `[foundry]`
   - `[smoke_tests]`
   - each `[[skills]]` block

3. Start the server and confirm the agent appears in `GET /`.

4. Smoke test the new slug.

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

- [README.md](/home/judacas/Documents/code/LLM-Automated-Inventory-Management/src/a2a_servers/README.md)
- [docs/architecture.md](/home/judacas/Documents/code/LLM-Automated-Inventory-Management/src/a2a_servers/docs/architecture.md)
- [agent_definition.py](/home/judacas/Documents/code/LLM-Automated-Inventory-Management/src/a2a_servers/agent_definition.py)
- [app_factory.py](/home/judacas/Documents/code/LLM-Automated-Inventory-Management/src/a2a_servers/app_factory.py)
- [foundry_agent_executor.py](/home/judacas/Documents/code/LLM-Automated-Inventory-Management/src/a2a_servers/foundry_agent_executor.py)
