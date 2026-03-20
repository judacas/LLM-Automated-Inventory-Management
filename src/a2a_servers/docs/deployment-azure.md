# Azure Deployment

## Scope

This document explains how to deploy `src/a2a_servers` to Azure based on the current state of this branch.

Important current-state note:

- there is no checked-in A2A-specific Bicep, Terraform, or `azure.yaml` for this package in this branch
- deployment is therefore a manual or team-scripted process today
- this document describes the recommended deployment shape so teammates and future agents do not assume infrastructure already exists

## Recommended Azure Hosting Choice

For the current package, the cleanest Azure target is a Linux web host that can run a long-lived ASGI process and expose HTTP routes publicly.

Recommended order:

1. Azure App Service for Linux
2. Azure Container Apps if your team prefers container-first hosting

App Service is usually the simplest fit here because:

- the app is an HTTP ASGI service
- it needs a stable public hostname for agent cards
- it does not currently require event-driven container orchestration
- the README already assumes an App Service-style host URL

## Required Azure Resources

At minimum, deployment needs:

- one Azure AI Foundry project with the target Foundry agents already created
- one Azure host for the A2A web process
- one managed identity or credential strategy that lets the host call the Foundry project
- environment configuration for the A2A server

Optional but recommended:

- Application Insights
- restricted inbound access if only team systems should call the service
- deployment slots or a staging environment

## Required App Settings

These settings must be present in the deployed app:

```dotenv
AZURE_AI_PROJECT_ENDPOINT=https://<your-ai-services>.services.ai.azure.com/api/projects/<your-project>
A2A_AGENT_CONFIG_DIR=agents
A2A_HOST=0.0.0.0
A2A_PORT=8000
A2A_URL_MODE=forwarded
A2A_FORWARDED_BASE_URL=https://<your-app-hostname>
LOG_LEVEL=INFO
```

Why these values differ from local defaults:

- cloud hosts should bind on `0.0.0.0`
- App Service and most reverse-proxied hosts should publish the external HTTPS URL, not the local bind address
- if the platform expects a particular port, set `A2A_PORT` to that port and make the startup command match

## Foundry Identity and Access

The runtime uses `DefaultAzureCredential`, so your Azure host must have a credential source it can use.

Recommended production approach:

- enable a system-assigned managed identity on the host
- grant that identity access needed to call the Azure AI Foundry project and underlying Azure AI resource

If managed identity is not configured, the app may work locally but fail in Azure because `DefaultAzureCredential` cannot find a usable credential chain.

## Packaging And Startup

### Option A: App Service from a flat `src/a2a_servers` zip

Zip the contents of `src/a2a_servers` so the artifact root contains files like:

- `__main__.py`
- `agent_definition.py`
- `app_factory.py`
- `agents/`
- `pyproject.toml`

Use a script-based startup command:

```bash
python3 __main__.py
```

You may add runtime flags if needed:

```bash
python __main__.py --host 0.0.0.0 --port 8000 --url-mode forwarded --forwarded-base-url https://<your-app-hostname>
```

You must ensure:

- dependencies are installed for `src/a2a_servers/pyproject.toml`
- the working directory is the deployed flat app root
- the `agents/` folder is included in the deployment artifact

### Option B: Container deployment

If you use Container Apps or a custom App Service container, build an image that:

- installs the package dependencies from `src/a2a_servers/pyproject.toml`
- copies the `src/a2a_servers` app directory
- sets the working directory to `src/a2a_servers`
- launches `python __main__.py` on the configured port

The repository's root [Dockerfile](/home/judacas/Documents/code/LLM-Automated-Inventory-Management/Dockerfile) is for `tool_api`, not for `a2a_servers`. Do not reuse it unchanged for this package.

## Suggested App Service Deployment Procedure

### 1. Prepare Foundry first

Before deploying the server, create or confirm:

- the Azure AI Foundry project
- the portal-managed agents referenced by TOML
- any tools or instructions configured on those Foundry agents

### 2. Create the web app

Create a Linux App Service or equivalent host.

Recommended baseline choices:

- Python-capable Linux host
- always-on enabled if available
- system-assigned managed identity enabled

### 3. Deploy the code

Deploy the repository or a deployment artifact that includes:

- the flat `src/a2a_servers` app contents
- the `agents/` folder

This app does not need the full repository when deployed in this flat layout.

### 4. Configure startup

Set the app startup command to launch the A2A package from the correct directory.

### 5. Configure environment variables

Set the required app settings listed earlier.

Most importantly:

- `AZURE_AI_PROJECT_ENDPOINT`
- `A2A_URL_MODE=forwarded`
- `A2A_FORWARDED_BASE_URL=https://<app-hostname>`

### 6. Verify routing

After deployment, verify:

- `GET /`
- `GET /<slug>/health`
- `GET /<slug>/.well-known/agent-card.json`

Make sure the card URL and route URLs point to the Azure hostname, not localhost.

### 7. Run an end-to-end smoke test

Use the checked-in `test_client.py` from a trusted environment and point it at the deployed hostname by matching the deployed card URLs.

## Container Apps Notes

Container Apps is a good option if your team wants:

- container-native deployment
- revision-based rollout
- tighter control over image build and startup

If you choose Container Apps:

- expose the app's HTTP ingress publicly or internally as needed
- set `A2A_URL_MODE=forwarded`
- set `A2A_FORWARDED_BASE_URL` to the Container Apps ingress FQDN
- ensure the container listens on the ingress target port

## Deployment Checklist

- Foundry project exists
- every TOML `foundry.agent_name` exists in that project
- Azure host identity can call Foundry
- `agents/` folder deployed with the app
- startup command uses `python __main__.py`
- `A2A_FORWARDED_BASE_URL` matches the real public hostname
- root index and agent cards are reachable after deploy

## What Is Not Automated Yet

The following are still missing from this branch and should be treated as future work rather than hidden assumptions:

- infrastructure-as-code for Azure resources
- deployment pipelines specific to `a2a_servers`
- secrets or identity provisioning automation
- environment promotion workflow

If the team wants reproducible deployment, the next step should be adding Azure IaC and a deployment workflow rather than expanding this manual document further.
