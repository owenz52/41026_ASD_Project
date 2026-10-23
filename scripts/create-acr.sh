
#!/usr/bin/env bash
set -Eeuo pipefail

# ============================================================
# Project: Create Azure Container Registry
# Resource Group: project-rg
# Location: australiaeast
#
# Run after:
#   1. scripts/env-setup.sh
#
# Run before:
#   2. scripts/build-images.sh
#
# This script creates the registry only.
# It does NOT build images or deploy applications.
# ============================================================

RESOURCE_GROUP="${RESOURCE_GROUP:-project-rg}"
EXPECTED_SUBSCRIPTION_ID="${EXPECTED_SUBSCRIPTION_ID:-4f004dab-3d26-4f85-bfd6-065fd3b81611}"
ACR_SKU="${ACR_SKU:-Basic}"

echo "=================================================="
echo " Azure Container Registry Setup"
echo "=================================================="

# Step 1: Check Azure CLI
if ! command -v az >/dev/null 2>&1; then
    echo "ERROR: Azure CLI is not installed or not on PATH." >&2
    exit 1
fi

# Step 2: Check Azure login
if ! az account show --output none 2>/dev/null; then
    echo "ERROR: Please log in using: az login" >&2
    exit 1
fi

# Step 3: Verify the intended subscription
CURRENT_SUBSCRIPTION_ID="$(
    az account show --query id --output tsv
)"

if [[ "$CURRENT_SUBSCRIPTION_ID" != "$EXPECTED_SUBSCRIPTION_ID" ]]; then
    echo "ERROR: Wrong Azure subscription selected." >&2
    echo "Expected: $EXPECTED_SUBSCRIPTION_ID" >&2
    echo "Current:  $CURRENT_SUBSCRIPTION_ID" >&2
    echo "Select the correct subscription before continuing." >&2
    exit 1
fi

echo "Subscription verified: $CURRENT_SUBSCRIPTION_ID"

# Step 4: Read resource group configuration
if ! az group show \
    --name "$RESOURCE_GROUP" \
    --output none 2>/dev/null; then
    echo "ERROR: Resource group '$RESOURCE_GROUP' was not found." >&2
    echo "Run scripts/env-setup.sh first." >&2
    exit 1
fi

REGISTRY_NAME="$(
    az group show \
        --name "$RESOURCE_GROUP" \
        --query "tags.registryName" \
        --output tsv
)"

LOCATION="$(
    az group show \
        --name "$RESOURCE_GROUP" \
        --query "tags.location" \
        --output tsv
)"

if [[ -z "$REGISTRY_NAME" || "$REGISTRY_NAME" == "None" ]]; then
    echo "ERROR: registryName tag is missing from '$RESOURCE_GROUP'." >&2
    exit 1
fi

if [[ -z "$LOCATION" || "$LOCATION" == "None" ]]; then
    LOCATION="${LOCATION:-australiaeast}"
fi

# Validate the registry name
if [[ ! "$REGISTRY_NAME" =~ ^[a-zA-Z0-9]{5,50}$ ]]; then
    echo "ERROR: Invalid registry name: $REGISTRY_NAME" >&2
    echo "ACR names must contain 5-50 alphanumeric characters." >&2
    exit 1
fi

echo "Resource group: $RESOURCE_GROUP"
echo "Location:       $LOCATION"
echo "Registry:       $REGISTRY_NAME"
echo "SKU:            $ACR_SKU"

# Step 5: Register the required resource provider
PROVIDER_STATE="$(
    az provider show \
        --namespace Microsoft.ContainerRegistry \
        --query registrationState \
        --output tsv
)"

if [[ "$PROVIDER_STATE" != "Registered" ]]; then
    echo "Registering Microsoft.ContainerRegistry..."
    az provider register \
        --namespace Microsoft.ContainerRegistry \
        --wait
fi

# Step 6: Reuse an existing registry or create it
if az acr show \
    --name "$REGISTRY_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --output none 2>/dev/null; then

    echo "Registry already exists. Reusing it."

else
    echo "Creating Azure Container Registry..."

    az acr create \
        --name "$REGISTRY_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --sku "$ACR_SKU" \
        --admin-enabled false \
        --output none

    echo "Registry creation command completed."
fi

# Step 7: Verify the registry
echo
echo "Verifying registry..."

az acr show \
    --name "$REGISTRY_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "{Name:name,LoginServer:loginServer,Location:location,Sku:sku.name,ProvisioningState:provisioningState,AdminEnabled:adminUserEnabled}" \
    --output table

echo
echo "=================================================="
echo " Container Registry Setup Finished"
echo "=================================================="
echo "Next step: review scripts/build-images.sh"
