# Adding Agents

## Purpose

This is the source of truth for adding a new A2A-mounted agent to `src/a2a_servers`.

Use this document when you want to expose another Azure AI Foundry agent through this server.

Do not use this document for:

- first-time local environment setup: see [developer-setup.md](./developer-setup.md)
- local public tunnel testing: see [local-testing-with-devtunnels.md](./local-testing-with-devtunnels.md)
- publishing a change to Azure: see [redeploying.md](./redeploying.md)

Important boundary:

- adding an agent to production does not require local developer setup
- adding an agent to production does not require Dev Tunnels
- it does require the Foundry agent to already exist and the deployed app to be redeployed with the updated TOML

## What You Are Actually Changing

This package does not create Foundry agents in code.

To add a new mounted agent, you are doing two separate things:

1. create or confirm the agent in Azure AI Foundry
2. add one new `*_agent.toml` definition so this server can expose it over A2A

The TOML definition is the source of truth for:

- the A2A route slug
- the published agent card metadata
- the mapping to the Foundry agent name
- the smoke-test prompts used by `test_client.py`

For the TOML schema details, see [agent-definition-reference.md](./agent-definition-reference.md).

## Prerequisites

Before editing this repo, confirm:

- the target Azure AI Foundry agent already exists
- you know its exact Foundry agent name
- you know the A2A-facing name, description, and skills you want to publish

If the Foundry agent name in TOML does not exactly match the portal-managed agent name, requests will fail at runtime.

## Procedure

### 1. Copy the template

From `src/a2a_servers`:

```bash
cp agents/agent.template.toml agents/<name>_agent.toml
```

Use `agents/<name>_agent.sample.toml` only for examples that should stay in the repo without loading at startup.

### 2. Fill in the agent definition

refer to [agent-definition-reference.md](./agent-definition-reference.md) to see how to set it up.

### 3. Validate locally

I'd recommend you test it locally since deployment takes time, refer to [local-testing-with-devtunnels.md](./local-testing-with-devtunnels.md).

### 5. Redeploy

The running Azure app only sees agent definitions that are in its deployed artifact.

After merging or preparing the TOML change, follow [redeploying.md](./redeploying.md).

> NOTE: Agent TOML definitions are currently located in the app service code.
This means that adding or modifying agents requires redeploying the application service.
For future plans on decoupling agent definitions from the deployment process,
refer to the [agents folder](../agents/) and check the README for the roadmap of upcoming changes.

## Production Change Summary

If your goal is only "add this agent to prod", the minimum path is:

1. create or confirm the Foundry agent in Azure AI Foundry
2. add the new `agents/<name>_agent.toml`
3. redeploy the A2A server with that updated file set
4. verify the deployed routes and agent card

That workflow does not require:

- `uv sync`
- local `.env` setup
- local server startup
- Dev Tunnels

## Related Documents

- setup only: [developer-setup.md](./developer-setup.md)
- deployment shape and Azure assumptions: [deployment-azure.md](./deployment-azure.md)
- redeploy checklist: [redeploying.md](./redeploying.md)
- Foundry runtime model: [foundry-integration.md](./foundry-integration.md)
- config schema: [agent-definition-reference.md](./agent-definition-reference.md)
- debugging: [troubleshooting.md](./troubleshooting.md)
