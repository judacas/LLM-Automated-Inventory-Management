# A2A Servers

This package hosts the project's Agent-to-Agent gateway layer. It runs a single ASGI process that discovers agent definitions from TOML files, mounts each one under its own A2A route, and forwards requests to named Azure AI Foundry agents.

This project uses a flat runtime layout: the server modules live directly under `src/a2a_servers`, and the app is started from that directory as a script rather than as an installed Python package.

In this branch, `src/a2a_servers` is primarily infrastructure for exposing Foundry agents over A2A. It is not the full business workflow by itself. The broader project goals still come from [projectOverview.md](/home/judacas/Documents/code/LLM-Automated-Inventory-Management/projectOverview.md), but this subrepo's responsibility is narrower:

- publish A2A agent cards and endpoints
- map each mounted A2A agent to a Foundry agent
- preserve conversation state across A2A requests by `context_id`
- provide a local smoke-test client and agent-definition contract

## Start Here

- Architecture: [docs/architecture.md](/home/judacas/Documents/code/LLM-Automated-Inventory-Management/src/a2a_servers/docs/architecture.md)
- Run locally and smoke test: [docs/runbook.md](/home/judacas/Documents/code/LLM-Automated-Inventory-Management/src/a2a_servers/docs/runbook.md)
- Deploy to Azure: [docs/deployment-azure.md](/home/judacas/Documents/code/LLM-Automated-Inventory-Management/src/a2a_servers/docs/deployment-azure.md)
- Azure AI Foundry integration: [docs/foundry-integration.md](/home/judacas/Documents/code/LLM-Automated-Inventory-Management/src/a2a_servers/docs/foundry-integration.md)
- Developer setup: [docs/developer-setup.md](/home/judacas/Documents/code/LLM-Automated-Inventory-Management/src/a2a_servers/docs/developer-setup.md)
- Agent definition contract: [docs/agent-definition-reference.md](/home/judacas/Documents/code/LLM-Automated-Inventory-Management/src/a2a_servers/docs/agent-definition-reference.md)
- Troubleshooting and known gaps: [docs/troubleshooting.md](/home/judacas/Documents/code/LLM-Automated-Inventory-Management/src/a2a_servers/docs/troubleshooting.md)

- All together: [/docs](/home/judacas/Documents/code/LLM-Automated-Inventory-Management/docs)

## Current State

- Multi-agent mounting is implemented and working locally along with manual deployment to azure.
- Foundry integration is dynamic by agent name, not hardcoded per route.
- Local smoke testing is included.
- Azure deployment infrastructure is not checked into this branch yet, so deployment is currently a documented manual process rather than an automated IaC workflow.

## Most Important Conventions

- Files matching `agents/*_agent.toml` are auto-discovered.
- Each config becomes a route prefix like `/<slug>/`.
- The published agent card URL changes based on `A2A_URL_MODE`.
- Duplicate slugs or duplicate Foundry agent names fail startup.
- The A2A server process does not create Foundry agents for you; it expects them to already exist.

## Current Limitations

- Conversation tracking is in-memory only. Restarting the process loses the A2A-to-Foundry conversation map.
- Foundry conversations remain open until cleanup or process shutdown.
- There is no checked-in Azure IaC for this package in the current branch.
- There is no built-in authentication or network restriction layer in this package itself; deployment must provide that boundary.
- The server assumes Foundry agents already exist and are correctly configured in Azure AI Foundry.

## What To Extend Next

The most natural future extension points are:

- persistent conversation storage instead of in-memory tracking
- deployment automation for Azure
- stronger auth and ingress controls
- richer health checks that validate Foundry connectivity
- more agent definitions that represent real project roles instead of examples
