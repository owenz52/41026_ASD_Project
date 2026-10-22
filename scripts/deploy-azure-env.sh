
#!/usr/bin/env bash
set -Eeuo pipefail

# ============================================================
# Project: Create Azure Container Apps Environment
#
# Resource Group: project-rg
# Location: Read from the resource group's location tag
# Environment: Read from the resource group's envName tag
#
# Run after:
#   1. scripts/env-setup.sh
#   2. scripts/build-images.sh
#
# Run before:
#   3. scripts/deploy-azure.sh
#
# This script creates or reuses the environment only.
# It does NOT deploy the 18 applications.
# ============================================================

RESOURCE_GROUP="${RESOURCE_GROUP:-project-rg}"
EXPECTED_SUBSCRIPTION_ID="${EXPECTED_SUBSCRIPTION_ID:-4f004dab-3d26-4f85-bfd6-065fd3b81611}"

trap 'echo "ERROR: Script failed near line ${LINENO}. Check the output above." >&2' ERR

echo "=================================================="
echo " Azure Container Apps Environment Setup"
echo "=================================================="

# ------------------------------------------------------------
# 1. Check prerequisites and Azure login
# ------------------------------------------------------------

if ! command -v az >/dev/null 2>&1; then
    echo "ERROR: Azure CLI (az) is not installed or not on PATH." >&2
    exit 1
fi

echo
echo "[1/5] Checking Azure login and subscription..."

if ! az account show --output none 2>/dev/null; then
    echo "ERROR: Please log in using: az login" >&2
    exit 1
fi

CURRENT_SUBSCRIPTION_ID="$(az account show --query id --output tsv)"

if [[ "$CURRENT_SUBSCRIPTION_ID" != "$EXPECTED_SUBSCRIPTION_ID" ]]; then
    echo "ERROR: Wrong Azure subscription selected." >&2
    echo "Expected: $EXPECTED_SUBSCRIPTION_ID" >&2
    echo "Current:  $CURRENT_SUBSCRIPTION_ID" >&2
    echo "Select the correct subscription before continuing." >&2
    exit 1
fi

echo "Azure subscription verified."

# ------------------------------------------------------------
# 2. Check resource group and read configuration tags
# ------------------------------------------------------------

echo
echo "[2/5] Checking resource group and configuration..."

if ! az group show --name "$RESOURCE_GROUP" --output none; then
    echo "ERROR: Resource group '$RESOURCE_GROUP' was not found." >&2
    exit 1
fi

LOCATION="$(az group show \
    --name "$RESOURCE_GROUP" \
    --query "tags.location" \
    --output tsv)"

ENV_NAME="$(az group show \
    --name "$RESOURCE_GROUP" \
    --query "tags.envName" \
    --output tsv)"

if [[ -z "$LOCATION" || "$LOCATION" == "None" ]]; then
    echo "ERROR: The resource group's location tag is missing." >&2
    exit 1
fi

if [[ -z "$ENV_NAME" || "$ENV_NAME" == "None" ]]; then
    echo "ERROR: The resource group's envName tag is missing." >&2
    exit 1
fi

echo "Resource group: $RESOURCE_GROUP"
echo "Location:      $LOCATION"
echo "Environment:   $ENV_NAME"

# ------------------------------------------------------------
# 3. Ensure required resource providers are registered
# ------------------------------------------------------------

echo
echo "[3/5] Checking resource providers..."

for provider in Microsoft.App Microsoft.OperationalInsights; do
    STATE="$(az provider show \
        --namespace "$provider" \
        --query registrationState \
        --output tsv)"

    if [[ "$STATE" != "Registered" ]]; then
        echo "$provider is '$STATE'. Requesting registration..."

        az provider register --namespace "$provider"

        echo "Waiting for $provider registration..."

        while true; do
            STATE="$(az provider show \
                --namespace "$provider" \
                --query registrationState \
                --output tsv)"

            if [[ "$STATE" == "Registered" ]]; then
                break
            fi

            if [[ "$STATE" == "RegistrationFailed" ]]; then
                echo "ERROR: Registration failed for $provider." >&2
                exit 1
            fi

            sleep 5
        done
    fi

    echo "$provider: Registered"
done

# ------------------------------------------------------------
# 4. Check Container Apps CLI extension
# ------------------------------------------------------------

echo
echo "[4/5] Checking Container Apps CLI extension..."

if ! az extension show --name containerapp --output none 2>/dev/null; then
    echo "Installing Container Apps CLI extension..."
    az extension add --name containerapp
else
    echo "Container Apps extension is installed."
fi

# ------------------------------------------------------------
# 5. Reuse or create the environment
# ------------------------------------------------------------

echo
echo "[5/5] Checking Container Apps environment..."

if az containerapp env show \
    --name "$ENV_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --output none 2>/dev/null; then

    echo "Environment '$ENV_NAME' already exists. Reusing it."

else
    echo "Creating environment '$ENV_NAME' in '$LOCATION'..."

    az containerapp env create \
        --name "$ENV_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --output none

    echo "Environment creation command completed."
fi

# ------------------------------------------------------------
# Final verification
# ------------------------------------------------------------

echo
echo "Verifying environment..."

az containerapp env show \
    --name "$ENV_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "{Name:name,Location:location,ProvisioningState:properties.provisioningState}" \
    --output table

echo
echo "=================================================="
echo " Container Apps Environment Setup Finished"
echo "=================================================="
echo "Next step: review scripts/deploy-azure.sh"
