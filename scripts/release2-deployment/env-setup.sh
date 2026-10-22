#!/bin/bash
set -euo pipefail

# Release 2 - Azure Environment Setup

RESOURCE_GROUP="${RESOURCE_GROUP:-asd-release2-rg}"
LOCATION="${LOCATION:-australiaeast}"

echo "=== Release 2 Azure Environment Setup ==="

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

# Step 2: Register required resource providers
echo "Registering Azure resource providers..."

az provider register --namespace Microsoft.App --wait
az provider register --namespace Microsoft.OperationalInsights --wait
az provider register --namespace Microsoft.ContainerRegistry --wait
az provider register --namespace Microsoft.Storage --wait

echo "Azure resource providers registered."

# Step 3: Create or reuse resource group
echo "Checking resource group: $RESOURCE_GROUP"

az group create \
    --name "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --output none

echo "Resource group ready."

# Step 4: Retrieve existing deployment resource names
REGISTRY_NAME=$(az group show \
    --name "$RESOURCE_GROUP" \
    --query "tags.registryName" \
    --output tsv)

ENV_NAME=$(az group show \
    --name "$RESOURCE_GROUP" \
    --query "tags.envName" \
    --output tsv)

# Step 5: Generate missing resource names

if [[ -z "$REGISTRY_NAME" || "$REGISTRY_NAME" == "None" ]]; then
    REGISTRY_NAME="asdr2registry${RANDOM}${RANDOM}"
fi

if [[ -z "$ENV_NAME" || "$ENV_NAME" == "None" ]]; then
    ENV_NAME="asd-r2-env-${RANDOM}"
fi

# Step 6: Store deployment names as resource group tags
echo "Saving deployment configuration..."

az group update \
    --name "$RESOURCE_GROUP" \
    --set \
        "tags.registryName=$REGISTRY_NAME" \
        "tags.envName=$ENV_NAME" \
        "tags.location=$LOCATION" \
    --output none

# Step 7: Display deployment configuration
echo ""
echo "=== Azure Environment Setup Complete ==="
echo "Resource Group: $RESOURCE_GROUP"
echo "Location: $LOCATION"
echo "Container Registry: $REGISTRY_NAME"
echo "Container Apps Environment: $ENV_NAME"
echo ""
echo "Resource group tags:"

az group show \
    --name "$RESOURCE_GROUP" \
    --query "tags" \
    --output table
