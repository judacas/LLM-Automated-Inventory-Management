# Architecture

## Purpose

`src/a2a_servers` is the transport and integration layer between:

- upstream A2A clients
- locally hosted A2A endpoints
- portal-managed Azure AI Foundry agents

The package does not define the full customer-service business system. Instead, it exposes one or more Foundry agents as A2A-compatible services so that other agents, apps, or orchestration layers can discover and call them through standard A2A routes.

## High-Level Runtime Model

One Python process hosts one Starlette app. That app mounts one sub-application per discovered agent definition.

```text
A2A client
  -> Starlette root app
    -> /<slug>/ mounted A2A app
      -> FoundryAgentExecutor
        -> FoundryAgentBackend
          -> Azure AI Foundry project endpoint
            -> named Foundry agent
```

This means:

- one process can expose multiple A2A agents
- each mounted agent has its own public identity and skills metadata
- all mounted agents share the same host process and Azure project endpoint
- each mounted agent can target a different Foundry agent name

## Main Components

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

Loads and validates `*_agent.toml` files. Sample files such as `*_agent.sample.toml` are not discovered.

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
- require Foundry endpoint env vars matching configured aliases
- generate per-agent base URLs and card URLs

The published URL model is important because A2A agent cards must advertise a URL that external callers can actually reach.

### `app_factory.py`

Builds the root Starlette app and one mounted A2A app per agent.

Responsibilities:

- create an `AgentCard` from the TOML definition
- build a Foundry backend factory for that agent
- create the A2A executor and request handler
- mount the A2A app under `/<slug>`
- add `GET /health` to each mounted agent
- expose a root `GET /` index listing loaded agents

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

For a typical request:

1. An A2A client sends a message to `POST /<slug>/`.
2. The mounted A2A app hands the request to `FoundryAgentExecutor`.
3. The executor converts incoming parts to plain text.
4. The executor looks up or creates a Foundry conversation for the current `context_id`.
5. The backend appends the user message to that Foundry conversation.
6. The backend calls the Foundry Responses API using `agent_reference.name`.
7. Streaming text deltas are forwarded back as A2A working updates.
8. The final combined text is emitted as the completed A2A task response.

## URL and Mounting Model

Each discovered agent is mounted at:

- `/<slug>/`

And typically exposes:

- `POST /<slug>/`
- `GET /<slug>/.well-known/agent-card.json`
- `GET /<slug>/.well-known/agent.json`
- `GET /<slug>/health`

The root app also exposes:

- `GET /`

That root endpoint is a convenience index, not an A2A route.

## Configuration Boundaries

There are two layers of configuration:

### Environment-level configuration

Examples:

- `AZURE_AI_PROJECT_ENDPOINT_<ALIAS_UPPER>` (per `foundry.endpoint_alias`)
- `A2A_HOST`
- `A2A_PORT`
- `A2A_URL_MODE`
- `A2A_FORWARDED_BASE_URL`
- `A2A_AGENT_CONFIG_DIR`

These values affect the whole host process.

### Agent-level configuration

Each live `*_agent.toml` defines:

- public A2A identity
- route slug
- user-facing skills metadata
- mapped Foundry agent name
- smoke test prompts

These values affect one mounted agent.

## Relationship to the Broader Project

Per the root [projectOverview.md](../../../projectOverview.md), the overall system is meant to support inventory, quoting, onboarding, purchasing, and an admin conversational surface.

In this branch, `src/a2a_servers` is best understood as enabling infrastructure for that system:

- it can expose quote-oriented and admin-oriented agents over A2A
- it can make Foundry-managed agents callable by other software components
- it does not yet implement the entire domain workflow end to end inside this package
