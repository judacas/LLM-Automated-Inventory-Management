# Quick Start: Azure Blob Storage Configuration

This guide provides the minimum steps to get agent configurations hosted on Azure Blob Storage.

## Prerequisites

- Azure subscription with appropriate permissions
- Azure CLI installed and authenticated (`az login`)
- Existing `src/a2a_servers` deployment or local development environment

## 5-Minute Setup

### 1. Create Storage Resources

```bash
# Set your variables
RESOURCE_GROUP="your-resource-group"
STORAGE_ACCOUNT="yourstorageaccount"  # Must be globally unique
LOCATION="eastus"  # Same as your App Service

# Create storage account (skip if already exists)
az storage account create \
    --name $STORAGE_ACCOUNT \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION \
    --sku Standard_LRS

# Create container
az storage container create \
    --name agent-configs \
    --account-name $STORAGE_ACCOUNT
```

### 2. Upload Configuration Files

```bash
# Upload all agent configs
cd src/a2a_servers/agents
for file in *_agent.toml; do
    if [[ ! "$file" == *".sample."* ]]; then
        az storage blob upload \
            --account-name $STORAGE_ACCOUNT \
            --container-name agent-configs \
            --name "$file" \
            --file "$file"
    fi
done
```

### 3. Configure Authentication

#### For Azure App Service (Managed Identity)

```bash
# Enable managed identity on App Service
APP_NAME="your-app-service-name"
az webapp identity assign \
    --resource-group $RESOURCE_GROUP \
    --name $APP_NAME

# Grant Storage Blob Data Reader role
PRINCIPAL_ID=$(az webapp identity show \
    --resource-group $RESOURCE_GROUP \
    --name $APP_NAME \
    --query principalId -o tsv)

STORAGE_ID=$(az storage account show \
    --name $STORAGE_ACCOUNT \
    --query id -o tsv)

az role assignment create \
    --assignee $PRINCIPAL_ID \
    --role "Storage Blob Data Reader" \
    --scope $STORAGE_ID

# Update app settings
az webapp config appsettings set \
    --resource-group $RESOURCE_GROUP \
    --name $APP_NAME \
    --settings \
        AZURE_BLOB_CONFIG_SOURCE=true \
        AZURE_STORAGE_ACCOUNT_URL=https://$STORAGE_ACCOUNT.blob.core.windows.net \
        AZURE_BLOB_CONTAINER_NAME=agent-configs

# Restart app
az webapp restart --resource-group $RESOURCE_GROUP --name $APP_NAME
```

#### For Local Development (Connection String)

```bash
# Get connection string
CONNECTION_STRING=$(az storage account show-connection-string \
    --name $STORAGE_ACCOUNT \
    --resource-group $RESOURCE_GROUP \
    --query connectionString -o tsv)

# Add to .env file
echo "AZURE_BLOB_CONFIG_SOURCE=true" >> .env
echo "AZURE_STORAGE_CONNECTION_STRING=\"$CONNECTION_STRING\"" >> .env
echo "AZURE_BLOB_CONTAINER_NAME=agent-configs" >> .env
```

### 4. Verify Setup

```bash
# Check configuration status
curl https://your-app.azurewebsites.net/config/status

# Or locally
curl http://localhost:10007/config/status
```

## Updating Configurations

### Update an Existing Agent

```bash
# Edit your TOML file locally
# Then upload
az storage blob upload \
    --account-name $STORAGE_ACCOUNT \
    --container-name agent-configs \
    --name quote_agent.toml \
    --file quote_agent.toml \
    --overwrite

# Changes take effect after cache TTL (default 60 seconds)
# No restart needed!
```

### Add a New Agent

```bash
# Upload new configuration
az storage blob upload \
    --account-name $STORAGE_ACCOUNT \
    --container-name agent-configs \
    --name new_agent.toml \
    --file new_agent.toml

# Restart app to mount new agent
az webapp restart --resource-group $RESOURCE_GROUP --name $APP_NAME
```

## Switching Between Local and Blob Storage

### Switch to Blob Storage

```bash
# Update app settings
az webapp config appsettings set \
    --resource-group $RESOURCE_GROUP \
    --name $APP_NAME \
    --settings AZURE_BLOB_CONFIG_SOURCE=true

az webapp restart --resource-group $RESOURCE_GROUP --name $APP_NAME
```

### Switch Back to Local Files

```bash
# Remove or set to false
az webapp config appsettings set \
    --resource-group $RESOURCE_GROUP \
    --name $APP_NAME \
    --settings AZURE_BLOB_CONFIG_SOURCE=false

az webapp restart --resource-group $RESOURCE_GROUP --name $APP_NAME
```

## Common Issues

### "Configuration loader not available"

**Fix**: Make sure you're using the updated `__main__.py` that creates the config_loader

### "Blob not found"

**Fix**: Verify blob names match pattern `*_agent.toml`:
```bash
az storage blob list \
    --account-name $STORAGE_ACCOUNT \
    --container-name agent-configs \
    --query "[].name"
```

### Changes not taking effect

**Fix**: Wait for cache TTL (60 seconds) or restart the app

## CLI Reference

### Run locally with Blob Storage

```bash
cd src/a2a_servers
python __main__.py --use-azure-blob
```

### Run with custom cache TTL

```bash
python __main__.py --use-azure-blob --config-cache-ttl 120
```

### Run with local files (default)

```bash
python __main__.py
```

## Next Steps

- See [azure-blob-configuration.md](azure-blob-configuration.md) for detailed documentation
- Set up Azure Dev Tunnels for local testing: [local-testing-with-devtunnels.md](local-testing-with-devtunnels.md)
- Enable blob versioning for configuration history
- Set up CI/CD to automatically upload configs on commit
