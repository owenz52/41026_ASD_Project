#!/usr/bin/env bash
set -Eeuo pipefail

# ============================================================
# Project: Create or Reuse Azure Container Apps Environment
#
# Reuses healthy environments and creates missing ones.
# Failed environments are preserved by default.
#
# Automatic deletion/recreation is opt-in:
#   AUTO_RECREATE_FAILED_ENV=true
#
# This script does NOT deploy the 18 applications.
# ============================================================

RESOURCE_GROUP="${RESOURCE_GROUP:-project-rg}"
EXPECTED_SUBSCRIPTION_ID="${EXPECTED_SUBSCRIPTION_ID:-4f004dab-3d26-4f85-bfd6-065fd3b81611}"
MAX_CREATE_ATTEMPTS="${MAX_CREATE_ATTEMPTS:-3}"
RETRY_DELAY_SECONDS="${RETRY_DELAY_SECONDS:-120}"
AUTO_RECREATE_FAILED_ENV="${AUTO_RECREATE_FAILED_ENV:-false}"
ENV_LOCATION="${ENV_LOCATION:-}"

trap 'echo "ERROR: Script failed near line ${LINENO}. Check the output above." >&2' ERR

die() {
    echo "ERROR: $*" >&2
    exit 1
}

# Validate configurable values.
[[ "$MAX_CREATE_ATTEMPTS" =~ ^[1-9][0-9]*$ ]] ||
    die "MAX_CREATE_ATTEMPTS must be a positive integer."

[[ "$RETRY_DELAY_SECONDS" =~ ^[0-9]+$ ]] ||
    die "RETRY_DELAY_SECONDS must be a non-negative integer."

case "${AUTO_RECREATE_FAILED_ENV,,}" in
    true|false) ;;
    *) die "AUTO_RECREATE_FAILED_ENV must be true or false." ;;
esac

echo "=================================================="
echo " Azure Container Apps Environment Setup"
echo "=================================================="

# ------------------------------------------------------------
# 1. Check prerequisites and Azure login
# ------------------------------------------------------------

command -v az >/dev/null 2>&1 ||
    die "Azure CLI (az) is not installed or not on PATH."

# Normalise CRLF output in Git Bash/Windows environments.
az() {
    command az "$@" | tr -d '\r'
}

echo
echo "[1/5] Checking Azure login and subscription..."

az account show --output none 2>/dev/null ||
    die "Please log in using: az login"

CURRENT_SUBSCRIPTION_ID="$(
    az account show --query id --output tsv
)" || die "Could not determine the active Azure subscription."

if [[ "$CURRENT_SUBSCRIPTION_ID" != "$EXPECTED_SUBSCRIPTION_ID" ]]; then
    echo "ERROR: Wrong Azure subscription selected." >&2
    echo "Expected: $EXPECTED_SUBSCRIPTION_ID" >&2
    echo "Current:  $CURRENT_SUBSCRIPTION_ID" >&2
    exit 1
fi

echo "Azure subscription verified."

# ------------------------------------------------------------
# 2. Read resource group configuration
# ------------------------------------------------------------

echo
echo "[2/5] Checking resource group and configuration..."

az group show \
    --name "$RESOURCE_GROUP" \
    --output none ||
    die "Resource group '$RESOURCE_GROUP' was not found or cannot be accessed."

TAG_LOCATION="$(
    az group show \
        --name "$RESOURCE_GROUP" \
        --query "tags.location" \
        --output tsv
)" || die "Could not read the resource group's location tag."

ENV_NAME="$(
    az group show \
        --name "$RESOURCE_GROUP" \
        --query "tags.envName" \
        --output tsv
)" || die "Could not read the resource group's envName tag."

if [[ -z "$TAG_LOCATION" || "$TAG_LOCATION" == "None" ]]; then
    die "The resource group's location tag is missing."
fi

if [[ -z "$ENV_NAME" || "$ENV_NAME" == "None" ]]; then
    die "The resource group's envName tag is missing."
fi

LOCATION="${ENV_LOCATION:-$TAG_LOCATION}"

echo "Resource group:             $RESOURCE_GROUP"
echo "Location:                   $LOCATION"
echo "Environment:                $ENV_NAME"
echo "Automatic failed-env repair: $AUTO_RECREATE_FAILED_ENV"

if [[ "$LOCATION" != "$TAG_LOCATION" ]]; then
    echo "NOTE: ENV_LOCATION overrides the location tag ($TAG_LOCATION)."
fi

# ------------------------------------------------------------
# 3. Ensure required resource providers are registered
# ------------------------------------------------------------

echo
echo "[3/5] Checking resource providers..."

for provider in Microsoft.App Microsoft.OperationalInsights; do
    STATE="$(
        az provider show \
            --namespace "$provider" \
            --query registrationState \
            --output tsv
    )" || die "Could not check registration state for $provider."

    if [[ "$STATE" != "Registered" ]]; then
        echo "$provider is '$STATE'. Requesting registration..."

        az provider register \
            --namespace "$provider" \
            --output none ||
            die "Could not request registration for $provider."

        echo "Waiting for $provider registration (up to 10 minutes)..."

        waited=0

        while true; do
            STATE="$(
                az provider show \
                    --namespace "$provider" \
                    --query registrationState \
                    --output tsv
            )" || die "Could not check registration state for $provider."

            [[ "$STATE" == "Registered" ]] && break

            [[ "$STATE" == "RegistrationFailed" ]] &&
                die "Registration failed for $provider."

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

    az extension add \
        --name containerapp \
        --output none ||
        die "Could not install the Container Apps CLI extension."
else
    echo "Container Apps extension is installed."
fi

# ------------------------------------------------------------
# 5. Environment state and safe recovery functions
# ------------------------------------------------------------

echo
echo "[5/5] Checking Container Apps environment..."

# Return MISSING only after a successful environment-list query
# confirms the environment is absent. Azure CLI errors are fatal
# to the caller rather than being interpreted as a missing env.

env_state() {
    local found state

    found="$(
        az containerapp env list \
            --resource-group "$RESOURCE_GROUP" \
            --query "[?name=='${ENV_NAME}'].name | [0]" \
            --output tsv
    )" || return 1

    if [[ -z "$found" || "$found" == "None" ]]; then
        printf '%s\n' "MISSING"
        return 0
    fi

    state="$(
        az containerapp env show \
            --name "$ENV_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --query properties.provisioningState \
            --output tsv
    )" || return 1

    if [[ -z "$state" || "$state" == "None" ]]; then
        return 1
    fi

    printf '%s\n' "$state"
}

env_error() {
    az containerapp env show \
        --name "$ENV_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.deploymentErrors" \
        --output tsv
}

# Refuse to delete the environment if the app list cannot be
# queried reliably. Count apps by comparing the full environment ID.

env_app_count() {
    local environment_id apps

    environment_id="$(
        az containerapp env show \
            --name "$ENV_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --query id \
            --output tsv
    )" || return 1

    [[ -n "$environment_id" && "$environment_id" != "None" ]] ||
        return 1

    apps="$(
        az containerapp list \
            --resource-group "$RESOURCE_GROUP" \
            --query "[?properties.managedEnvironmentId=='${environment_id}'] | length(@)" \
            --output tsv
    )" || return 1

    [[ "$apps" =~ ^[0-9]+$ ]] || return 1

    printf '%s\n' "$apps"
}

delete_env() {
    local apps state waited

    if [[ "${AUTO_RECREATE_FAILED_ENV,,}" != "true" ]]; then
        die "Automatic recovery is disabled. Inspect the environment first. Set AUTO_RECREATE_FAILED_ENV=true only if you intend to allow deletion."
    fi

    apps="$(env_app_count)" ||
        die "Could not reliably count apps in '$ENV_NAME'. Refusing to delete it."

    if (( apps > 0 )); then
        die "Environment '$ENV_NAME' has $apps app(s). Refusing to delete it automatically."
    fi

    echo "No apps detected. Deleting failed environment '$ENV_NAME'..."

    az containerapp env delete \
        --name "$ENV_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --yes \
        --output none ||
        die "Could not delete environment '$ENV_NAME'."

    # Confirm deletion before attempting to recreate the environment.
    waited=0

    while true; do
        state="$(env_state)" ||
            die "Could not verify whether '$ENV_NAME' was deleted."

        [[ "$state" == "MISSING" ]] && break

        if (( waited >= 1200 )); then
            die "Timed out waiting for environment deletion (state: $state)."
        fi

        echo "Waiting for environment deletion (state: $state)..."
        sleep 15
        waited=$((waited + 15))
    done

    echo "Environment deletion confirmed."
}

# Wait for an in-progress environment to reach a terminal state.
# The final state is printed to stdout; progress messages go to stderr.

wait_for_terminal_state() {
    local waited=0 state

    while true; do
        state="$(env_state)" ||
            die "Could not check the environment's provisioning state."

        case "$state" in
            Succeeded|Failed|Canceled|UpgradeFailed|MISSING)
                printf '%s\n' "$state"
                return 0
                ;;
        esac

        if (( waited >= 1200 )); then
            die "Timed out waiting for environment (state: $state)."
        fi

        echo "Environment is '$state'. Waiting..." >&2
        sleep 15
        waited=$((waited + 15))
    done
}

STATE="$(env_state)" ||
    die "Could not reliably determine whether the environment exists."

if [[ "$STATE" != "MISSING" ]]; then
    STATE="$(wait_for_terminal_state)"
fi

case "$STATE" in
    Succeeded)
        echo "Environment '$ENV_NAME' is healthy. Reusing it."
        ;;

    UpgradeFailed)
        die "Environment '$ENV_NAME' is in state UpgradeFailed. Investigate it in the Azure portal; it will not be deleted."
        ;;

    Failed|Canceled)
        echo "Environment '$ENV_NAME' is in state '$STATE'."

        ERR_MSG="$(env_error)" ||
            die "Could not retrieve environment error details."

        if [[ -n "$ERR_MSG" && "$ERR_MSG" != "None" ]]; then
            echo "Reason: $ERR_MSG"
        fi

        if [[ "${AUTO_RECREATE_FAILED_ENV,,}" != "true" ]]; then
            die "Environment preserved. Investigate it before recovery. To permit deletion, rerun with AUTO_RECREATE_FAILED_ENV=true."
        fi

        delete_env
        STATE="MISSING"
        ;;

    MISSING)
        echo "Environment '$ENV_NAME' does not exist. It will be created."
        ;;

    *)
        die "Unexpected environment state: $STATE"
        ;;
esac

# ------------------------------------------------------------
# Create missing environment, retrying transient failures
# ------------------------------------------------------------

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
            echo "The create command reported an error; checking Azure's actual state."
        fi

        STATE="$(wait_for_terminal_state)"

        if [[ "$STATE" == "Succeeded" ]]; then
            echo "Environment is ready."
            break
        fi

        if [[ "$STATE" == "UpgradeFailed" ]]; then
            die "Environment entered UpgradeFailed. Investigate it in the Azure portal."
        fi

        if [[ "$STATE" == "Failed" || "$STATE" == "Canceled" ]]; then
            ERR_MSG="$(env_error)" ||
                die "Could not retrieve environment error details."

            [[ -n "$ERR_MSG" && "$ERR_MSG" != "None" ]] &&
                echo "Reason: $ERR_MSG"

            if [[ "${AUTO_RECREATE_FAILED_ENV,,}" != "true" ]]; then
                die "Creation failed. The environment has been preserved. Investigate it before retrying or enable AUTO_RECREATE_FAILED_ENV=true after confirming deletion is safe."
            fi

            delete_env
        elif [[ "$STATE" != "MISSING" ]]; then
            die "Unexpected environment state after creation: $STATE"
        fi

        if (( attempt == MAX_CREATE_ATTEMPTS )); then
            die "Environment creation did not succeed after ${MAX_CREATE_ATTEMPTS} attempts. Check Azure Service Health and the deployment error details."
        fi

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

FINAL_STATE="$(env_state)" ||
    die "Could not verify the final environment state."

[[ "$FINAL_STATE" == "Succeeded" ]] ||
    die "Environment is in state '$FINAL_STATE', not Succeeded."

echo
echo "=================================================="
echo " Container Apps Environment Setup Finished"
echo "=================================================="
echo "Environment: $ENV_NAME"
echo "Location:    $LOCATION"
echo "Status:      Succeeded"
echo
echo "Next steps:"
echo "  ./scripts/preflight-check.sh"
echo "  ./scripts/deploy-azure-apps.sh"