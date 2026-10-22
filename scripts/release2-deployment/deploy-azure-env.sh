#!/bin/bash
set -euo pipefail

# Release 2 - Azure Container Apps Environment

RESOURCE_GROUP="${RESOURCE_GROUP:-asd-release2-rg}"

echo "=== Release 2 Container Apps Environment Setup ==="

# Step 1: Verify Azure CLI authentication
echo "Checking Azure CLI authentication..."

if ! command -v az >/dev/null 2>&1; then
    echo "ERROR: Azure CLI is not installed." >&2
    exit 1
fi

if ! az account show >/dev/null 2>&1; then
    echo "ERROR: Not logged into Azure. Run 'az login' first." >&2
    exit 1
fi

echo "Azure CLI authentication verified."

# Step 2: Read resource names from Azure resource group tags
echo "Retrieving Azure deployment configuration..."

if ! az group exists --name "$RESOURCE_GROUP" --output tsv | grep -qi '^true$'; then
    echo "ERROR: Resource group '$RESOURCE_GROUP' does not exist." >&2
    echo "Run env-setup.sh first." >&2
    exit 1
fi

ENV_NAME=$(az group show \
    --name "$RESOURCE_GROUP" \
    --query "tags.envName" \
    --output tsv)

LOCATION=$(az group show \
    --name "$RESOURCE_GROUP" \
    --query "tags.location" \
    --output tsv)

if [[ -z "$ENV_NAME" || "$ENV_NAME" == "None" ||
      -z "$LOCATION" || "$LOCATION" == "None" ]]; then
    echo "ERROR: Required resource group tags are missing." >&2
    echo "Run env-setup.sh first." >&2
    exit 1
fi

echo "Resource Group: $RESOURCE_GROUP"
echo "Environment: $ENV_NAME"
echo "Location: $LOCATION"

# Step 3: Create or reuse the Container Apps environment
echo "Checking existing Container Apps environment..."

if az containerapp env show \
    --name "$ENV_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --output none 2>/dev/null; then

    echo "Existing Container Apps environment found. Reusing it."

else
    echo "Creating Container Apps environment..."

    az containerapp env create \
        --name "$ENV_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --output none

    echo "Container Apps environment created."
fi

# Step 4: Verify environment provisioning
echo "Verifying Container Apps environment..."

PROVISIONING_STATE=$(az containerapp env show \
    --name "$ENV_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "properties.provisioningState" \
    --output tsv)

if [[ "$PROVISIONING_STATE" != "Succeeded" ]]; then
    echo "ERROR: Environment provisioning state: $PROVISIONING_STATE" >&2
    exit 1
fi

# Step 5: Display environment details
echo ""
echo "=== Container Apps Environment Ready ==="
echo "Resource Group: $RESOURCE_GROUP"
echo "Environment: $ENV_NAME"
echo "Location: $LOCATION"
echo "Provisioning State: $PROVISIONING_STATE"
