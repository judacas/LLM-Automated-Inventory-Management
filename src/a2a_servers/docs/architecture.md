# Architecture

## Purpose

`src/a2a_servers` is the transport and integration layer between:

- upstream A2A clients
- locally hosted A2A endpoints
- portal-managed Azure AI Foundry agents

The package does not define the full customer-service business system. Instead, it exposes one or more Foundry agents as A2A-compatible services so that other agents, apps, or orchestration layers can discover and call them through standard A2A routes.

It also supports **grouped endpoints** that act as A2A routers: a single URL that can represent several individual agent endpoints, routing each incoming request to the correct one based on a `[target:SLUG]` marker in the message.

## High-Level Runtime Model

One Python process hosts one Starlette app. That app mounts one sub-application per discovered agent or group definition.

```text
A2A client
  -> Starlette root app
    -> /<slug>/ mounted A2A app          (individual agent)
      -> FoundryAgentExecutor
        -> FoundryAgentBackend
          -> Azure AI Foundry project endpoint
            -> named Foundry agent

    -> /<group-slug>/ mounted A2A app    (grouped endpoint)
      -> GroupRouterExecutor
        -> parse [target:SLUG] from message
        -> httpx A2A call to http://localhost:<port>/<slug>/
          -> FoundryAgentExecutor (individual agent)
            -> FoundryAgentBackend
              -> Azure AI Foundry project endpoint
                -> named Foundry agent
```

This means:

- one process can expose multiple A2A agents
- each mounted agent has its own public identity and skills metadata
- all mounted agents share the same host process and Azure project endpoint
- each mounted agent can target a different Foundry agent name
- grouped endpoints do **not** call Foundry directly; they route to individual endpoints via A2A

## Main Components

### `group_definition.py`

Loads and validates `*_group.toml` files.

Responsibilities:

- discover group configs from `A2A_AGENT_CONFIG_DIR` or the default `agents/`
- validate required `[a2a]`, `[group]`, and `[[skills]]` sections
- validate `group.agents` is a non-empty list of agent slugs
- derive or normalize the route slug (strips `_group` / `-group` suffixes)
- reject duplicate group slugs
- return an empty tuple if no `*_group.toml` files exist (groups are optional)

### `group_router_executor.py`

Routes grouped A2A endpoint requests to individual agent endpoints.

Responsibilities:

- parse `[target:SLUG]` from incoming message text using regex
- validate SLUG against the group's allowed `member_slugs`
- forward the full A2A message to `http://localhost:<port>/<slug>/` using
  an outbound `A2AClient.send_message_streaming()` call
- re-emit downstream streaming deltas as working-state task updates
- complete the task with the full concatenated response text
- return clear error messages if the target is missing, invalid, or unreachable

### `__main__.py`

Entry point for the server.

Responsibilities:

- load `.env`
- resolve runtime settings
- load agent definitions from disk
- construct the app
- log published URLs and startup metadata
- start `uvicorn`

### `agent_definition.py`

Loads and validates `*_agent.toml` files.

Responsibilities:

- discover agent configs from `A2A_AGENT_CONFIG_DIR` or the default `agents/`
- validate required `[a2a]`, `[foundry]`, `[[skills]]`, and optional `[smoke_tests]`
- derive or normalize the route slug
- reject duplicate slugs
- reject duplicate Foundry agent names

This module defines the contract that human contributors and future LLM agents must follow when adding new agents.

### `settings.py`

Loads server settings from environment variables.

Key responsibilities:

- bind host and port
- resolve whether published URLs are local or proxy-facing
- require `AZURE_AI_PROJECT_ENDPOINT`
- generate per-agent base URLs and card URLs

The published URL model is important because A2A agent cards must advertise a URL that external callers can actually reach.

### `app_factory.py`

Builds the root Starlette app and one mounted A2A app per agent or group.

Responsibilities:

- create an `AgentCard` from the TOML definition
- for individual agents: build a Foundry backend factory and create a `FoundryAgentExecutor`
- for grouped endpoints: create a `GroupRouterExecutor` wired to the local URL factory
- validate that group member slugs reference known individual agent slugs (startup error if not)
- validate that no group slug collides with an individual agent slug
- mount each A2A app under `/<slug>`
- add `GET /health` to each mounted agent or group
- expose a root `GET /` index listing all loaded agents and groups

### `foundry_agent_executor.py`

Bridges A2A requests to the Foundry backend.

Responsibilities:

- convert A2A message parts into text
- create and reuse Foundry conversations per A2A `context_id`
- stream Foundry output back as A2A task updates
- mark task success or failure

Important behavior:

- `context_id` is the conversation key
- if `task_id` or `context_id` is missing, fallback IDs are generated
- conversation tracking is in memory only

### `foundry_agent.py`

Async wrapper over the Azure AI Projects SDK.

Responsibilities:

- authenticate using `DefaultAzureCredential`
- connect to the configured Azure AI Foundry project endpoint
- verify that the named Foundry agent exists
- create conversations
- append user messages
- request streamed or non-streamed responses
- clean up conversations and SDK clients

## Request Flow

### Individual agent request

1. An A2A client sends a message to `POST /<slug>/`.
2. The mounted A2A app hands the request to `FoundryAgentExecutor`.
3. The executor converts incoming parts to plain text.
4. The executor looks up or creates a Foundry conversation for the current `context_id`.
5. The backend appends the user message to that Foundry conversation.
6. The backend calls the Foundry Responses API using `agent_reference.name`.
7. Streaming text deltas are forwarded back as A2A working updates.
8. The final combined text is emitted as the completed A2A task response.

### Grouped endpoint request

1. An A2A client sends a message to `POST /<group-slug>/`.
2. The mounted A2A app hands the request to `GroupRouterExecutor`.
3. The executor extracts message text and searches for `[target:SLUG]`.
4. If no marker is found or the slug is not in the group's allowed set, the
   task is failed with a clear error message.
5. The executor makes an outbound A2A streaming call to
   `http://localhost:<port>/<slug>/` (the individual agent endpoint).
6. Streaming chunks from the downstream agent are re-emitted as working updates.
7. The final combined text is emitted as the completed A2A task response.

See [grouped-endpoint-input-contract.md](grouped-endpoint-input-contract.md) for
the expected message format and orchestrator prompt guidance.

## URL and Mounting Model

Each discovered agent or group is mounted at:

- `/<slug>/`

And typically exposes:

- `POST /<slug>/`
- `GET /<slug>/.well-known/agent-card.json`
- `GET /<slug>/.well-known/agent.json`
- `GET /<slug>/health`

The root app also exposes:

- `GET /`

That root endpoint is a convenience index listing all mounted agents and groups,
not an A2A route.

Grouped endpoint self-calls always use the local URL (`http://localhost:<port>/<slug>`)
regardless of the configured `A2A_URL_MODE`, so forwarded-URL deployments work correctly.

## Configuration Boundaries

There are two layers of configuration:

### Environment-level configuration

Examples:

- `AZURE_AI_PROJECT_ENDPOINT`
- `A2A_HOST`
- `A2A_PORT`
- `A2A_URL_MODE`
- `A2A_FORWARDED_BASE_URL`
- `A2A_AGENT_CONFIG_DIR`

These values affect the whole host process.

### Agent-level configuration

Each `*_agent.toml` defines:

- public A2A identity
- route slug
- user-facing skills metadata
- mapped Foundry agent name
- smoke test prompts

These values affect one mounted agent.

## Relationship to the Broader Project

Per the root [projectOverview.md](/home/judacas/Documents/code/LLM-Automated-Inventory-Management/projectOverview.md), the overall system is meant to support inventory, quoting, onboarding, purchasing, and an admin conversational surface.

In this branch, `src/a2a_servers` is best understood as enabling infrastructure for that system:

- it can expose quote-oriented and admin-oriented agents over A2A
- it can make Foundry-managed agents callable by other software components
- it does not yet implement the entire domain workflow end to end inside this package
