# Foundry Integration

## What This Package Assumes

`src/a2a_servers` does not create Foundry agents in code. It connects to a pre-existing Azure AI Foundry project and forwards requests to agents that were already created and configured in the Foundry portal.

That means the order of operations is:

1. create and configure the Foundry agent in Azure AI Foundry
2. add or update the matching `*_agent.toml`
3. run or deploy the A2A server

For the step-by-step workflow for adding a new mounted agent, use [adding-agents.md](./adding-agents.md).

## Core Mapping

Each mounted A2A agent maps to one Foundry agent name:

- TOML field: `foundry.agent_name`
- runtime call target: `agent_reference.name`

Examples in this branch:

- `quote_agent.toml` -> `quote-agent`
- `math_agent.sample.toml` -> sample config for `Math-Agent`

If the name is wrong, the runtime will fail when it verifies or calls that Foundry agent.

## Required Environment Variable

The package requires:

```dotenv
AZURE_AI_PROJECT_ENDPOINT=https://<your-ai-services>.services.ai.azure.com/api/projects/<your-project>
```

This is the Azure AI Foundry project endpoint, not just a model endpoint.

## Authentication Model

The runtime authenticates with:

- `azure.identity.aio.DefaultAzureCredential`

So Foundry access works only if the environment provides a valid Azure credential source.

Typical local development options:

- `az login`
- IDE Azure sign-in
- environment-based credentials

Typical Azure hosting option:

- managed identity

## Runtime Behavior

### Initialization

When a mounted agent backend is initialized, the package:

- creates an `AIProjectClient`
- gets an OpenAI-compatible client from that project
- verifies the configured Foundry agent is reachable by `agent_name`

### Conversation Handling

For each distinct A2A `context_id`, the executor creates or reuses one Foundry conversation.

Behavior details:

- new `context_id` -> new Foundry conversation
- repeated `context_id` -> existing Foundry conversation reused
- conversation IDs are stored in memory only

This gives a reasonable conversation model for demos and local development, but it is not durable across restarts.

### Messaging

For each user request:

- the user's A2A message is converted to text
- that text is appended to the Foundry conversation
- the runtime calls the Foundry Responses API
- the Foundry response is streamed back as A2A task updates

## What Must Be Configured In Foundry

The A2A server only handles transport and proxying. The actual agent behavior still lives in Foundry.

Each Foundry agent should be configured with:

- clear instructions
- the intended tools
- the desired model selection
- any guardrails or policies your team requires

For example:

- a quote agent should know how to answer quoting and availability questions
- a math agent may be configured with Code Interpreter

## Adding New Foundry Agents

The implementation rule is simple:

- Foundry is the source of truth for agent behavior
- `*_agent.toml` is the source of truth for A2A identity and routing

Use [adding-agents.md](./adding-agents.md) for the actual procedure.

## Integrating With Foundry-Orchestrated Systems

Other systems can consume these A2A endpoints in two main ways:

- as direct HTTP A2A endpoints using the agent card and mounted routes
- as callable external agents from a broader multi-agent orchestration layer

When another team member or agent asks "how do I call the Foundry model?", the correct answer here is usually:

- do not call the model directly from this package
- call the A2A endpoint for the mounted agent
- let this package route the request to the configured Foundry agent

That keeps A2A identity, skills metadata, and route conventions in one place.

## Important Design Constraint

All mounted A2A agents in one process share the same `AZURE_AI_PROJECT_ENDPOINT`.

Implications:

- you can map different slugs to different Foundry agents
- you cannot, in the current implementation, map different slugs to different Foundry projects without changing the code

If that becomes necessary, the configuration model will need to move project endpoint selection down to the per-agent level.

## Known Gaps

- No persistent conversation store
- No per-agent Foundry project override
- No built-in validation of whether Foundry tools are configured correctly beyond agent lookup
- No automated provisioning of Foundry agents from this package

## Recommended Team Workflow

For stable collaboration:

- treat the Foundry portal as the source of truth for agent behavior
- treat `*_agent.toml` as the source of truth for live A2A identity and discovery metadata
- keep the Foundry agent name and TOML config in sync
- add smoke-test prompts whenever a new agent is introduced

## Fixing duplicate A2A tool names

When multiple A2A server connections are added in the Foundry portal, each tool is created with the default name `remote protocol`, which triggers a “duplicate tool argument name” error when one client connects to more than one server. Use the helper commands to inspect and fix the schema:

```bash
# Inspect the current schema
python -m a2a_servers.foundry_agent_tools show-tools \
  --agent-name <foundry-agent-name-or-id> \
  --endpoint "$AZURE_AI_PROJECT_ENDPOINT"

# Rename tools so each gets a unique name (use --dry-run to preview)
python -m a2a_servers.foundry_agent_tools rename-tools \
  --agent-name <foundry-agent-name-or-id> \
  --prefix <short-prefix> \
  --endpoint "$AZURE_AI_PROJECT_ENDPOINT"
```

- The command fetches the latest version (or a specific `--version`), applies unique names to every tool (and `server_label` when present), and publishes a new agent version.
- Use `show-tools` after renaming to verify the schema that Foundry exposes to clients.

## Creating an agent fully in code (with pre-named A2A tools)

You can create a Foundry prompt agent directly in code, avoiding duplicate tool names from the start. Supply the A2A endpoints inline:

```bash
python -m a2a_servers.foundry_agent_tools create-agent \
  --agent-name <desired-agent-name> \
  --model-deployment <model-deployment-name> \
  --instructions-path path/to/instructions.txt \
  --a2a-tool "name=quote,base_url=https://<a2a-host>/quote,connection_id=<portal-connection-id>" \
  --a2a-tool "name=purchase,base_url=https://<a2a-host>/purchase,connection_id=<portal-connection-id>" \
  --endpoint "$AZURE_AI_PROJECT_ENDPOINT"
```

- Each `--a2a-tool` value is a comma-separated string with required `base_url` and `connection_id`, plus optional `name` and `agent_card_path`. Tool names are slugified and de-duplicated automatically (use `--tool-name-prefix` to control the generated prefix).
- The command creates or updates the agent by publishing a new version backed by the supplied model deployment and instructions file.

## How to test these changes yourself

1. Export `AZURE_AI_PROJECT_ENDPOINT` and sign in with `az login` (or another `DefaultAzureCredential` source).
2. Run `python -m a2a_servers.foundry_agent_tools show-tools --agent-name <name> --endpoint "$AZURE_AI_PROJECT_ENDPOINT"` to confirm connectivity.
3. Use `rename-tools --dry-run` first, then run without `--dry-run` to publish the fixed schema.
4. For code-first creation, point `--instructions-path` to your instructions and pass one `--a2a-tool` per A2A endpoint.
5. Re-run `show-tools` to verify the published tool schema.

These commands only call the Azure AI Projects SDK; they do not need access to your A2A servers from this repository. Run them in an environment that has credentials for your Foundry project.
