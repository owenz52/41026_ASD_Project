#!/bin/bash
set -euo pipefail

# Release 2 - Azure Resource Cleanup

# Deletes the Release 2 Azure resource group and all resources
# contained within it.
#
# WARNING:
# This permanently removes Container Apps, container images,
# storage resources, and potentially all application data.

RESOURCE_GROUP="${RESOURCE_GROUP:-asd-release2-rg}"

echo "=== Release 2 Azure Resource Cleanup ==="

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

# Step 2: Verify the resource group exists
echo "Checking resource group: $RESOURCE_GROUP"

if ! az group exists \
    --name "$RESOURCE_GROUP" \
    --output tsv | grep -qi '^true$'; then

    echo "Resource group '$RESOURCE_GROUP' does not exist."
    echo "No cleanup required."
    exit 0
fi

# Step 3: Display the active subscription and resources
SUBSCRIPTION_NAME=$(az account show --query name --output tsv)
SUBSCRIPTION_ID=$(az account show --query id --output tsv)

echo ""
echo "Azure Subscription: $SUBSCRIPTION_NAME"
echo "Subscription ID: $SUBSCRIPTION_ID"
echo "Resource Group: $RESOURCE_GROUP"

echo ""
echo "Resources scheduled for deletion:"

az resource list \
    --resource-group "$RESOURCE_GROUP" \
    --output table

# Step 4: Require explicit confirmation
echo ""
echo "WARNING: This operation deletes the entire resource group."
echo "All resources and data within the group may be lost."
echo ""
read -r -p "Type DELETE $RESOURCE_GROUP to confirm: " CONFIRMATION

if [[ "$CONFIRMATION" != "DELETE $RESOURCE_GROUP" ]]; then
    echo "Cleanup cancelled. No resources were deleted."
    exit 0
fi

# Step 5: Delete the resource group
echo ""
echo "Deleting resource group: $RESOURCE_GROUP"

az group delete \
    --name "$RESOURCE_GROUP" \
    --yes

# Step 6: Verify deletion
echo "Verifying resource group deletion..."

if az group exists \
    --name "$RESOURCE_GROUP" \
    --output tsv | grep -qi '^true$'; then

    echo "ERROR: Resource group still exists." >&2
    exit 1
fi

echo ""
echo "=== Release 2 Azure Cleanup Complete ==="
echo "Deleted Resource Group: $RESOURCE_GROUP"
