# A2A Servers

This package hosts the project's Agent-to-Agent gateway layer. It runs a single ASGI process that discovers agent definitions from TOML files, mounts each one under its own A2A route, and forwards requests to named Azure AI Foundry agents.

This project uses a flat runtime layout: the server modules live directly under `src/a2a_servers`, and the app is started from that directory as a script rather than as an installed Python package.

In this branch, `src/a2a_servers` is primarily infrastructure for exposing Foundry agents over A2A. It is not the full business workflow by itself. The broader project goals still come from [projectOverview.md](../../projectOverview.md), but this subrepo's responsibility is narrower:

- publish A2A agent cards and endpoints
- map each mounted A2A agent to a Foundry agent
- preserve conversation state across A2A requests by `context_id`
- provide a local smoke-test client and agent-definition contract

## Start Here

- Architecture: [docs/architecture.md](docs/architecture.md)
- Developer setup: [docs/developer-setup.md](docs/developer-setup.md)
- Add a new agent: [docs/adding-agents.md](docs/adding-agents.md)
- Redeploy after a change: [docs/redeploying.md](docs/redeploying.md)
- Local testing with Dev Tunnels: [docs/local-testing-with-devtunnels.md](docs/local-testing-with-devtunnels.md)
- Run locally and smoke test: [docs/runbook.md](docs/runbook.md)
- Deploy to Azure: [docs/deployment-azure.md](docs/deployment-azure.md)
- Azure AI Foundry integration: [docs/foundry-integration.md](docs/foundry-integration.md)
- Agent definition contract: [docs/agent-definition-reference.md](docs/agent-definition-reference.md)
- Troubleshooting and known gaps: [docs/troubleshooting.md](docs/troubleshooting.md)

- All together: [/docs](../../docs)

## Current State

- Multi-agent mounting is implemented and working locally along with manual deployment to azure.
- Foundry integration is dynamic by agent name, not hardcoded per route.
- Local smoke testing is included.
- Azure deployment infrastructure is not checked into this branch yet, so deployment is currently a documented manual process rather than an automated IaC workflow.
- each server can be easily added as a remote agent in foundry
- pytest not updated and currently fails to do import overhaul

## Most Important Conventions

- Files matching `agents/*_agent.toml` are auto-discovered.
- Sample configs should use a name like `agents/*_agent.sample.toml` so they are kept in-repo but not loaded at startup.
- Each config becomes a route prefix like `/<slug>/`.
- The published agent card URL changes based on `A2A_URL_MODE`.
- Duplicate slugs or duplicate Foundry agent names fail startup.
- The A2A server process does not create Foundry agents for you; it expects them to already exist.
- adding or changing an agent in production requires a redeploy

## Current Limitations

- Conversation tracking is in-memory only. Restarting the process loses the A2A-to-Foundry conversation map.
- **each client can only connect to one remote agent at a time, this is believed to be a foundry support of a2a issue, not how the servers are set up**
- Foundry conversations remain open until cleanup or process shutdown.
- There is no checked-in Azure IaC for this package in the current branch.
- There is no built-in authentication or network restriction layer in this package itself; deployment must provide that boundary.
- The server assumes Foundry agents already exist and are correctly configured in Azure AI Foundry.
- need to redeploy to add new agents

## Composite (Single-Endpoint) Mode

Azure AI Foundry currently allows a client to connect to only one A2A server at a time. To expose multiple agents through a single endpoint, set `A2A_COMPOSITE_SLUG` (or pass `--composite-slug`) and the server will:

- publish one combined agent card using `A2A_COMPOSITE_NAME`, `A2A_COMPOSITE_DESCRIPTION`, `A2A_COMPOSITE_VERSION`, and `A2A_COMPOSITE_HEALTH_MESSAGE` (all optional)
- merge the skills from every discovered agent
- route incoming requests to the correct Foundry agent using a keyword pre-processor

Add optional `routing_keywords` to skills to make routing explicit:

```toml
[[skills]]
id = "inventory"
name = "Inventory"
description = "Check and update stock"
routing_keywords = ["inventory", "stock", "items"]
```

If no routing keywords are provided, the router falls back to the skill id, name, and tags. Single-agent configurations continue to work unchanged.

## What To Extend Next

The most natural future extension points are:

- persistent conversation storage in DB instead of in-memory tracking
- deployment automation for Azure
- stronger auth and ingress controls
- richer health checks that validate Foundry connectivity
- better process for adding and removeing agents, potentially with a gui
