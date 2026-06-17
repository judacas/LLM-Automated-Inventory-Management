# Hosting Agent Configurations Outside The App Artifact

## Purpose

This guide explains how to decouple A2A agent definitions from the deployed web app so that adding or tweaking an agent no longer requires redeploying the code. It covers how to package the `*_agent.toml` files, host them in Azure Blob Storage, configure the runtime to pull them, and test that setup locally (with or without Dev Tunnels).

## Quick Path

1. Package the configs:

   ```bash
   cd src/a2a_servers
   zip -r agents.zip agents
   ```

2. Upload `agents.zip` to an Azure Storage container (public read or SAS).

3. Set `A2A_AGENT_CONFIG_URL=https://<storage-account>.blob.core.windows.net/<container>/agents.zip[?<sas>]` on the host. This takes precedence over `A2A_AGENT_CONFIG_DIR`.

4. Restart the app. `GET /` should show the agents from the downloaded bundle.

5. To test locally, serve `agents.zip` over HTTP (or via a Dev Tunnel) and point `A2A_AGENT_CONFIG_URL` at that URL.

## Packaging The Config Bundle

- The runtime expects a `.zip` file whose contents include one or more files named `*_agent.toml`.
- You can keep the `agents/` folder name inside the archive or place the TOML files at the root; the loader will locate the first folder that contains matching files.

Recommended packaging command from `src/a2a_servers`:

```bash
zip -r agents.zip agents
```

This preserves the existing folder name and keeps any `.sample.toml` files out of the archive if you omit them.

## Hosting In Azure Blob Storage

Create or reuse a storage account and container:

```bash
az storage container create --account-name <account> --name agent-configs --auth-mode login
```

Upload the archive:

```bash
az storage blob upload \
  --account-name <account> \
  --container-name agent-configs \
  --name agents.zip \
  --file agents.zip \
  --overwrite \
  --auth-mode login
```

Make it readable:

- simplest: set the container to blob-level public access if your org allows it, or
- preferred: generate a limited SAS token (read-only, short-lived, IP-scoped if possible) and append it to the blob URL

Resulting URL shape:

```text
https://<account>.blob.core.windows.net/agent-configs/agents.zip?<sas-token>
```

## Configure The Runtime

Set the new app setting (App Service, container env, or local `.env`):

```dotenv
A2A_AGENT_CONFIG_URL=https://<account>.blob.core.windows.net/agent-configs/agents.zip?<sas>
```

Behavior:

- If `A2A_AGENT_CONFIG_URL` is set, the server downloads and extracts the archive at startup.
- If the URL is empty, it falls back to `A2A_AGENT_CONFIG_DIR` or the bundled `agents/` directory.
- The URL must end in `.zip` and be reachable with read access from the running host.

You no longer need to include the `agents/` folder in the deployment artifact when using the URL-based approach.

## Local And Dev Tunnel Testing

You can verify the hosted archive without touching Azure:

```bash
cd /path/to/archive
python -m http.server 8000

# in another shell
cd src/a2a_servers
export A2A_AGENT_CONFIG_URL=http://localhost:8000/agents.zip
uv run python __main__.py
```

To share the same local archive via Dev Tunnels:

```bash
devtunnel create a2a-configs -a
devtunnel port create -p 8000 --protocol http
devtunnel host a2a-configs

export A2A_AGENT_CONFIG_URL=https://<tunnel-host>/agents.zip
uv run python __main__.py
```

Then point `test_client.py` or Foundry at the tunnel URL.

## Update Cycle Checklist

1. Edit or add `*_agent.toml` locally.
2. Regenerate `agents.zip`.
3. Upload the new archive to the storage container (overwrite existing blob).
4. Restart the App Service/container. No code redeploy is required.
5. Validate `GET /` and `GET /<slug>/health` on the deployed host.
