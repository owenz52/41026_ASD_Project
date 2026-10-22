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
#   2. scripts/create-acr.sh
#   3. scripts/build-images.sh
#
# Run before:
#   4. scripts/preflight-check.sh
#   5. scripts/deploy-azure-apps.sh
#
# This script creates or reuses the environment only.
# It does NOT deploy the 18 applications.
#
# Behaviour:
#   Succeeded      -> reused
#   Missing        -> created
#   Failed/Canceled-> deleted and recreated, but ONLY if no apps
#                     live in it (it refuses otherwise)
#   In progress    -> waited on (up to 20 minutes)
#   Creation fails -> retried (Azure sometimes returns transient
#                     "managed cluster failed, retry later" errors)
#
# Optional environment variables:
#   RESOURCE_GROUP, EXPECTED_SUBSCRIPTION_ID
#   ENV_LOCATION         create the environment in a different region
#                        than the resource group's location tag
#   MAX_CREATE_ATTEMPTS  default 3
#   RETRY_DELAY_SECONDS  default 120
# ============================================================

RESOURCE_GROUP="${RESOURCE_GROUP:-project-rg}"
EXPECTED_SUBSCRIPTION_ID="${EXPECTED_SUBSCRIPTION_ID:-4f004dab-3d26-4f85-bfd6-065fd3b81611}"
MAX_CREATE_ATTEMPTS="${MAX_CREATE_ATTEMPTS:-3}"
RETRY_DELAY_SECONDS="${RETRY_DELAY_SECONDS:-120}"

trap 'echo "ERROR: Script failed near line ${LINENO}. Check the output above." >&2' ERR

die() {
    echo "ERROR: $*" >&2
    exit 1
}

echo "=================================================="
echo " Azure Container Apps Environment Setup"
echo "=================================================="

# ------------------------------------------------------------
# 1. Check prerequisites and Azure login
# ------------------------------------------------------------

command -v az >/dev/null 2>&1 ||
    die "Azure CLI (az) is not installed or not on PATH."

# Some Azure CLI installs (Git Bash/Windows) emit CRLF line endings,
# which silently corrupts values read with $(...). Strip them.
# Defined AFTER the "az is installed" check so that check still works.
az() { command az "$@" | tr -d '\r'; }

echo
echo "[1/5] Checking Azure login and subscription..."

if ! az account show --output none 2>/dev/null; then
    die "Please log in using: az login"
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

az group show --name "$RESOURCE_GROUP" --output none ||
    die "Resource group '$RESOURCE_GROUP' was not found."

TAG_LOCATION="$(az group show \
    --name "$RESOURCE_GROUP" \
    --query "tags.location" \
    --output tsv)"

ENV_NAME="$(az group show \
    --name "$RESOURCE_GROUP" \
    --query "tags.envName" \
    --output tsv)"

if [[ -z "$TAG_LOCATION" || "$TAG_LOCATION" == "None" ]]; then
    die "The resource group's location tag is missing."
fi

if [[ -z "$ENV_NAME" || "$ENV_NAME" == "None" ]]; then
    die "The resource group's envName tag is missing."
fi

LOCATION="${ENV_LOCATION:-$TAG_LOCATION}"

echo "Resource group: $RESOURCE_GROUP"
echo "Location:       $LOCATION"
echo "Environment:    $ENV_NAME"

if [[ "$LOCATION" != "$TAG_LOCATION" ]]; then
    echo "NOTE: ENV_LOCATION overrides the resource group's location tag ($TAG_LOCATION)."
    echo "      Apps in this environment will run in $LOCATION."
fi

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

        az provider register --namespace "$provider" --output none

        echo "Waiting for $provider registration (up to 10 minutes)..."

        waited=0
        while true; do
            STATE="$(az provider show \
                --namespace "$provider" \
                --query registrationState \
                --output tsv)"

            [[ "$STATE" == "Registered" ]] && break

            if [[ "$STATE" == "RegistrationFailed" ]]; then
                die "Registration failed for $provider."
            fi

            if (( waited >= 600 )); then
                die "Timed out waiting for $provider registration (state: $STATE)."
            fi

            sleep 5
            waited=$((waited + 5))
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
    az extension add --name containerapp --output none
else
    echo "Container Apps extension is installed."
fi

# ------------------------------------------------------------
# 5. Reuse, repair, or create the environment
# ------------------------------------------------------------

echo
echo "[5/5] Checking Container Apps environment..."

env_state() {
    az containerapp env show \
        --name "$ENV_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query properties.provisioningState \
        --output tsv 2>/dev/null || true
}

env_app_count() {
    az containerapp list \
        --resource-group "$RESOURCE_GROUP" \
        --query "length([?ends_with(properties.managedEnvironmentId, '/managedEnvironments/${ENV_NAME}')])" \
        --output tsv 2>/dev/null || echo "0"
}

env_error() {
    az containerapp env show \
        --name "$ENV_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.deploymentErrors" \
        --output tsv 2>/dev/null || true
}

delete_env() {
    local apps
    apps="$(env_app_count)"
    [[ -z "$apps" || "$apps" == "None" ]] && apps=0

    if (( apps > 0 )); then
        die "Environment '$ENV_NAME' has $apps app(s) in it. Refusing to delete it automatically. Delete or move them first."
    fi

    echo "Deleting environment '$ENV_NAME' (this can take several minutes)..."
    az containerapp env delete \
        --name "$ENV_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --yes \
        --output none

    if [[ -n "$(env_state)" ]]; then
        die "Environment '$ENV_NAME' still exists after deletion. Check the portal."
    fi

    echo "Environment deleted."
}

wait_for_terminal_state() {
    local waited=0 state
    while true; do
        state="$(env_state)"
        case "$state" in
            Succeeded|Failed|Canceled|UpgradeFailed|"")
                return 0 ;;
        esac

        if (( waited >= 1200 )); then
            die "Timed out waiting for environment (state: $state)."
        fi

        echo "  Environment is '$state'. Waiting..."
        sleep 15
        waited=$((waited + 15))
    done
}

wait_for_terminal_state
STATE="$(env_state)"

case "$STATE" in
    Succeeded)
        echo "Environment '$ENV_NAME' already exists and is healthy. Reusing it."
        ;;

    UpgradeFailed)
        die "Environment '$ENV_NAME' is in state 'UpgradeFailed'. Investigate in the portal; it was not deleted."
        ;;

    Failed|Canceled)
        echo "Environment '$ENV_NAME' is in state '$STATE' and cannot be used."
        ERR_MSG="$(env_error)"
        [[ -n "$ERR_MSG" && "$ERR_MSG" != "None" ]] && echo "Reason: $ERR_MSG"
        delete_env
        STATE=""
        ;;
esac

if [[ "$STATE" != "Succeeded" ]]; then
    attempt=1

    while (( attempt <= MAX_CREATE_ATTEMPTS )); do
        echo
        echo "Creating environment '$ENV_NAME' in '$LOCATION' (attempt ${attempt}/${MAX_CREATE_ATTEMPTS})..."

        if ! az containerapp env create \
            --name "$ENV_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --location "$LOCATION" \
            --output none; then
            echo "The create command reported an error."
        fi

        STATE="$(env_state)"

        if [[ "$STATE" == "Succeeded" ]]; then
            echo "Environment created successfully."
            break
        fi

        ERR_MSG="$(env_error)"
        echo "Environment state: ${STATE:-not created}"
        [[ -n "$ERR_MSG" && "$ERR_MSG" != "None" ]] && echo "Reason: $ERR_MSG"

        if (( attempt == MAX_CREATE_ATTEMPTS )); then
            echo "ERROR: Environment creation failed after ${MAX_CREATE_ATTEMPTS} attempts." >&2
            echo "  - Check Azure Service Health for Container Apps incidents in $LOCATION." >&2
            echo "  - Try another region:  ENV_LOCATION=australiasoutheast ./scripts/deploy-azure-env.sh" >&2
            echo "  - If it keeps failing, open an Azure support ticket with the error above." >&2
            exit 1
        fi

        [[ -n "$STATE" ]] && delete_env

        echo "Waiting ${RETRY_DELAY_SECONDS}s before retrying..."
        sleep "$RETRY_DELAY_SECONDS"
        attempt=$((attempt + 1))
    done
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

FINAL_STATE="$(env_state)"
[[ "$FINAL_STATE" == "Succeeded" ]] ||
    die "Environment is in state '${FINAL_STATE:-missing}', not Succeeded."

echo
echo "=================================================="
echo " Container Apps Environment Setup Finished"
echo "=================================================="
echo "Next steps:"
echo "  ./scripts/preflight-check.sh"
echo "  ./scripts/deploy-azure-apps.sh"