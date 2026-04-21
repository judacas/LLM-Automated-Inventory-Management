# Local Testing With Dev Tunnels

## Purpose

This document is the source of truth for testing `src/a2a_servers` locally through a public URL by using Azure Dev Tunnels.

Use this when:

- you want Azure AI Foundry or another remote caller to reach your local machine
- you want to verify that published agent cards advertise a public URL

Do not use this for:

- first-time local setup: see [developer-setup.md](./developer-setup.md)
- adding a new agent: see [adding-agents.md](./adding-agents.md)
- production deployment: see [redeploying.md](./redeploying.md)

Important boundary:

- Dev Tunnels are for local testing only
- Dev Tunnels are not part of the production path for adding agents
- you need Dev Tunnels if you want foundry models to call your local a2aServer (for quick changes and tests not production)

## Prerequisites

Before using this guide, complete the local setup in [developer-setup.md](./developer-setup.md).

You need:

- a working local `.env`
- local Azure authentication that `DefaultAzureCredential` can use
- at least one valid `*_agent.toml`
- devtunnels setup, [how to install and use the devtunnel CLI](https://learn.microsoft.com/en-us/azure/developer/dev-tunnels/get-started)

## Local Settings Required For Tunnel Testing

In `src/a2a_servers/.env`, set:

```dotenv
A2A_URL_MODE=forwarded
```

> **Note:** You'll set `A2A_FORWARDED_BASE_URL` in the next section after creating your dev tunnel.
Leave it unset for now.

Keep the normal local bind settings:

```dotenv
A2A_HOST=localhost
A2A_PORT=10007
```

Why this matters:

- the server still listens locally
- the published agent card URLs switch to the public forwarded host

## Dev Tunnel Flow

Example:

```bash
devtunnel user login
devtunnel create my-a2a-agent -a
devtunnel port create -p 10007 --protocol http
devtunnel host my-a2a-agent
```

Copy the printed HTTPS host and set:

```dotenv
A2A_FORWARDED_BASE_URL=https://<your-tunnel-host>
```

Then restart the A2A server.

## Start The Server

From `src/a2a_servers`:

```bash
uv run python __main__.py
```

After startup, verify that the published URLs use the tunnel host rather than `localhost`.

## What To Check

Verify:

- `GET /` lists the expected agents
- `GET /<slug>/health` works locally
- `GET /<slug>/.well-known/agent-card.json` shows the tunnel hostname

If the card still shows `localhost`, the most common cause is that the server was not restarted after updating `.env`.

## Smoke Test Through The Tunnel

From `src/a2a_servers`:

```bash
uv run python test_client.py --agent-slug <slug> --base-url https://<your-tunnel-host>
```

This verifies the public URL path rather than the local-only URL path.

## Common Failure Modes

- the tunnel host in `.env` does not match the current tunnel
- `devtunnel` is forwarding a different port than `A2A_PORT`
- the A2A server was started before `A2A_FORWARDED_BASE_URL` was updated
- the configured TOML points to a Foundry agent name that does not exist

For deeper troubleshooting, see [troubleshooting.md](./troubleshooting.md).

## Related Documents

- local setup: [developer-setup.md](./developer-setup.md)
- add a new agent: [adding-agents.md](./adding-agents.md)
- local/server checks: [runbook.md](./runbook.md)
- troubleshooting: [troubleshooting.md](./troubleshooting.md)
