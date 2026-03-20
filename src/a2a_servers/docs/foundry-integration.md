# Foundry Integration

## What This Package Assumes

`src/a2a_servers` does not create Foundry agents in code. It connects to a pre-existing Azure AI Foundry project and forwards requests to agents that were already created and configured in the Foundry portal.

That means the order of operations is:

1. create and configure the Foundry agent in Azure AI Foundry
2. add or update the matching `*_agent.toml`
3. run or deploy the A2A server

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

## Integrating New Foundry Agents

To expose a new Foundry agent through this package:

1. Create or confirm the Foundry agent in the Azure AI Foundry portal.
2. Copy [agents/agent.template.toml](/home/judacas/Documents/code/LLM-Automated-Inventory-Management/src/a2a_servers/agents/agent.template.toml) to a new `*_agent.toml` file.
   Use `*_agent.sample.toml` instead if you want an example that should not be auto-discovered.
3. Set `foundry.agent_name` to the exact Foundry agent name.
4. Fill in the `a2a` metadata and `[[skills]]` blocks.
5. Add realistic `[smoke_tests].prompts`.
6. Start the server and verify the new slug appears at `GET /`.
7. Run `uv run test_client.py --agent-slug <slug>`.

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
