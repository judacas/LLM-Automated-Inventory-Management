# Azure Blob Storage Configuration

## Overview

This document explains how to host agent configuration files in Azure Blob Storage, allowing you to update agent configurations without redeploying the entire application.

## Benefits

- **Decoupled Deployment**: Update agent configurations independently from the application code
- **Quick Changes**: Modify agent settings and see effects after cache expiration (default 60 seconds)
- **Centralized Management**: Store all agent configs in one place accessible by multiple environments
- **Version Control**: Use Azure Blob versioning for configuration history
- **No Downtime**: Changes take effect after cache TTL without restarting the application

## Architecture

The system supports two configuration sources:

1. **Local Filesystem** (default): Reads `*_agent.toml` files from `agents/` directory
2. **Azure Blob Storage**: Reads `*_agent.toml` files from Azure Blob Storage container

The configuration loader includes:
- Automatic caching with configurable TTL (default 60 seconds)
- Support for both connection string and managed identity authentication
- Transparent fallback behavior
- Configuration diagnostics endpoint at `/config/status`

## Azure Setup

### Step 1: Create a Storage Account

1. In Azure Portal, navigate to **Storage Accounts**
2. Click **Create**
3. Fill in the required fields:
   - **Resource Group**: Select or create a resource group
   - **Storage Account Name**: Choose a unique name (e.g., `contosoagentconfigs`)
   - **Region**: Same as your App Service for better performance
   - **Performance**: Standard
   - **Redundancy**: LRS (Locally Redundant Storage) is sufficient for configs
4. Click **Review + Create**, then **Create**

### Step 2: Create a Blob Container

1. Navigate to your storage account
2. Go to **Containers** under **Data storage**
3. Click **+ Container**
4. Set:
   - **Name**: `agent-configs` (or your preferred name)
   - **Public access level**: Private (no anonymous access)
5. Click **Create**

### Step 3: Upload Agent Configuration Files

You have two options:

#### Option A: Using Azure Portal

1. Navigate to your container
2. Click **Upload**
3. Select your `*_agent.toml` files from `src/a2a_servers/agents/`
4. Upload all files that don't have `.sample.` in the name

#### Option B: Using Azure CLI

```bash
# Set variables
STORAGE_ACCOUNT="contosoagentconfigs"
CONTAINER="agent-configs"

# Upload all agent config files
cd src/a2a_servers/agents
for file in *_agent.toml; do
    if [[ ! "$file" == *".sample."* ]]; then
        az storage blob upload \
            --account-name $STORAGE_ACCOUNT \
            --container-name $CONTAINER \
            --name "$file" \
            --file "$file"
    fi
done
```

### Step 4: Configure Authentication

You have two authentication options:

#### Option A: Managed Identity (Recommended for Production)

1. **Enable System-Assigned Managed Identity** on your App Service:
   ```bash
   az webapp identity assign \
       --resource-group <resource-group> \
       --name <app-service-name>
   ```

2. **Grant Storage Blob Data Reader role** to the managed identity:
   ```bash
   # Get the principal ID
   PRINCIPAL_ID=$(az webapp identity show \
       --resource-group <resource-group> \
       --name <app-service-name> \
       --query principalId -o tsv)

   # Get the storage account resource ID
   STORAGE_ID=$(az storage account show \
       --name <storage-account-name> \
       --query id -o tsv)

   # Assign the role
   az role assignment create \
       --assignee $PRINCIPAL_ID \
       --role "Storage Blob Data Reader" \
       --scope $STORAGE_ID
   ```

3. **Set environment variables** in App Service Configuration:
   ```
   AZURE_BLOB_CONFIG_SOURCE=true
   AZURE_STORAGE_ACCOUNT_URL=https://<storage-account-name>.blob.core.windows.net
   AZURE_BLOB_CONTAINER_NAME=agent-configs
   ```

#### Option B: Connection String (For Development/Testing)

1. **Get the connection string**:
   - Go to Storage Account → Access Keys
   - Copy one of the connection strings

2. **Set environment variables**:
   ```
   AZURE_BLOB_CONFIG_SOURCE=true
   AZURE_STORAGE_CONNECTION_STRING=<connection-string>
   AZURE_BLOB_CONTAINER_NAME=agent-configs
   ```

   **Security Note**: Never commit connection strings to source control. Use Azure Key Vault or App Service Configuration for production.

### Step 5: Configure App Service

Update your App Service configuration:

```bash
az webapp config appsettings set \
    --resource-group <resource-group> \
    --name <app-service-name> \
    --settings \
        AZURE_BLOB_CONFIG_SOURCE=true \
        AZURE_STORAGE_ACCOUNT_URL=https://<storage-account-name>.blob.core.windows.net \
        AZURE_BLOB_CONTAINER_NAME=agent-configs
```

Restart the app:

```bash
az webapp restart \
    --resource-group <resource-group> \
    --name <app-service-name>
```

## Local Testing

### Testing with Local Blob Storage Emulator (Azurite)

1. **Install Azurite** (local Azure Storage emulator):
   ```bash
   npm install -g azurite
   ```

2. **Start Azurite**:
   ```bash
   azurite --silent --location ./azurite-data
   ```

3. **Upload test configs to Azurite**:
   ```bash
   # Create container
   az storage container create \
       --name agent-configs \
       --connection-string "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"

   # Upload configs
   cd src/a2a_servers/agents
   for file in *_agent.toml; do
       if [[ ! "$file" == *".sample."* ]]; then
           az storage blob upload \
               --container-name agent-configs \
               --name "$file" \
               --file "$file" \
               --connection-string "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
       fi
   done
   ```

4. **Update `.env`**:
   ```
   AZURE_BLOB_CONFIG_SOURCE=true
   AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;
   AZURE_BLOB_CONTAINER_NAME=agent-configs
   ```

5. **Run the server**:
   ```bash
   cd src/a2a_servers
   python __main__.py
   ```

### Testing with Azure Dev Tunnels

Azure Dev Tunnels allow you to expose your local server to the internet securely, making it easy to test with remote Foundry agents.

1. **Install Dev Tunnels CLI**:
   ```bash
   # Windows
   winget install Microsoft.devtunnel

   # macOS/Linux
   curl -sL https://aka.ms/DevTunnelCliInstall | bash
   ```

2. **Login**:
   ```bash
   devtunnel user login
   ```

3. **Create a tunnel**:
   ```bash
   devtunnel create --allow-anonymous
   ```

4. **Start the tunnel** (in one terminal):
   ```bash
   devtunnel port create -p 10007
   devtunnel host
   ```

   Note the tunnel URL (e.g., `https://abc123.devtunnels.ms`)

5. **Update `.env`** (in another terminal):
   ```
   A2A_URL_MODE=forwarded
   A2A_FORWARDED_BASE_URL=https://abc123.devtunnels.ms
   AZURE_BLOB_CONFIG_SOURCE=true
   # ... other Azure Blob config
   ```

6. **Start the server**:
   ```bash
   cd src/a2a_servers
   python __main__.py
   ```

7. **Test configuration endpoint**:
   ```bash
   curl https://abc123.devtunnels.ms/config/status
   ```

## Configuration Management Workflow

### Adding a New Agent

1. **Create the TOML file** locally (e.g., `new_agent.toml`)
2. **Upload to Azure Blob Storage**:
   ```bash
   az storage blob upload \
       --account-name <storage-account-name> \
       --container-name agent-configs \
       --name new_agent.toml \
       --file new_agent.toml
   ```
3. **Wait for cache TTL** (default 60 seconds) or restart the app
4. **Verify** the new agent appears at `GET /`

### Updating an Agent Configuration

1. **Edit the TOML file** locally
2. **Upload the updated file**:
   ```bash
   az storage blob upload \
       --account-name <storage-account-name> \
       --container-name agent-configs \
       --name existing_agent.toml \
       --file existing_agent.toml \
       --overwrite
   ```
3. **Wait for cache TTL** or restart the app
4. **Verify** changes at `GET /<slug>/.well-known/agent-card.json`

### Removing an Agent

1. **Delete the blob**:
   ```bash
   az storage blob delete \
       --account-name <storage-account-name> \
       --container-name agent-configs \
       --name agent_to_remove.toml
   ```
2. **Restart the app** (removal requires restart, as agents are mounted at startup)

## Monitoring and Diagnostics

### Configuration Status Endpoint

Check configuration source and status:

```bash
curl http://localhost:10007/config/status
```

Example response:
```json
{
  "configuration": {
    "source_type": "azure_blob_storage",
    "loaded_at": "2026-03-23T19:30:00.000Z",
    "file_count": 4,
    "source_info": {
      "type": "azure_blob_storage",
      "container": "agent-configs",
      "prefix": "(root)"
    }
  },
  "agents_loaded": 4
}
```

### Azure Portal Monitoring

1. **View blob access logs**:
   - Storage Account → Monitoring → Logs
   - Query: `StorageBlobLogs | where OperationName == "GetBlob"`

2. **Enable diagnostics** for detailed logging:
   ```bash
   az monitor diagnostic-settings create \
       --resource <storage-account-resource-id> \
       --name blob-diagnostics \
       --logs '[{"category": "StorageRead", "enabled": true}]' \
       --workspace <log-analytics-workspace-id>
   ```

## Performance Considerations

### Cache TTL

- **Default**: 60 seconds
- **Adjust via CLI**: `python __main__.py --config-cache-ttl 120`
- **Adjust via env**: Not currently supported; use CLI flag

**Recommendations**:
- **Production**: 60-300 seconds (balance between freshness and API calls)
- **Development**: 10-30 seconds (faster iteration)
- **Staging**: 60 seconds (match production)

### Blob Storage Performance

- **Standard tier** is sufficient for configuration files
- **Same region** as App Service reduces latency
- **Redundancy**: LRS is sufficient (configs can be rebuilt from source control)

## Security Best Practices

1. **Use Managed Identity** in production (avoid connection strings)
2. **Least Privilege**: Grant only "Storage Blob Data Reader" role
3. **Private Endpoints**: For enhanced security, use private endpoints for Blob Storage
4. **Enable Blob Versioning**: Allows rollback of configuration changes
5. **Audit Logging**: Enable diagnostic settings to track configuration access
6. **Secrets in Configs**: Never store secrets in TOML files; use Azure Key Vault

## Troubleshooting

### "Configuration loader not available"

**Cause**: Using old synchronous loader
**Solution**: Ensure the app is started with the updated `__main__.py` that creates the config_loader

### "AZURE_STORAGE_ACCOUNT_URL required"

**Cause**: Using managed identity without setting the account URL
**Solution**: Set `AZURE_STORAGE_ACCOUNT_URL` environment variable

### "Blob not found"

**Cause**: File name mismatch or missing file
**Solution**:
- Verify blob name matches pattern `*_agent.toml`
- Check blob prefix configuration
- Use Azure Portal to verify blob exists

### Stale Configuration

**Cause**: Cache hasn't expired yet
**Solution**:
- Wait for cache TTL to expire
- Restart the application
- Reduce `--config-cache-ttl` for faster iteration during development

## Migration Guide

### Migrating from Local Filesystem to Azure Blob

1. **Create Azure resources** (storage account, container)
2. **Upload existing configs**:
   ```bash
   cd src/a2a_servers/agents
   for file in *_agent.toml; do
       if [[ ! "$file" == *".sample."* ]]; then
           az storage blob upload \
               --account-name <storage-account-name> \
               --container-name agent-configs \
               --name "$file" \
               --file "$file"
       fi
   done
   ```
3. **Update App Service configuration** (see Step 5 above)
4. **Restart the app**
5. **Verify** at `/config/status` endpoint
6. **Test** all agent endpoints

### Rolling Back to Local Filesystem

Simply set `AZURE_BLOB_CONFIG_SOURCE=false` (or remove it) and restart the app. The system will automatically fall back to reading from the local `agents/` directory.

## FAQ

**Q: Do I need to restart the app when I change a configuration?**
A: No, changes take effect after the cache TTL expires (default 60 seconds). However, adding or removing agents requires a restart because agents are mounted at startup.

**Q: Can I use a folder structure in my blob container?**
A: Yes, set the `AZURE_BLOB_PREFIX` environment variable to the folder path (e.g., `configs/production`).

**Q: What happens if Azure Blob Storage is unavailable?**
A: The app will fail to start if it can't load configurations at startup. Consider implementing a local fallback or ensuring high availability for your storage account.

**Q: Can I test locally without Azure?**
A: Yes, use Azurite (local emulator) as described in the "Local Testing" section.

**Q: How do I know which configuration source is being used?**
A: Check the `/config/status` endpoint or look at the startup logs which show the configuration source type.

## Next Steps

- Set up **Azure Blob versioning** for configuration history
- Implement **CI/CD pipeline** to automatically upload configs
- Configure **Azure Monitor alerts** for configuration access failures
- Add **integration tests** for configuration loading
