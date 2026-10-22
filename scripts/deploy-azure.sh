
#!/usr/bin/env bash
set -Eeuo pipefail

# ============================================================
# Project: Deploy 18 services to Azure Container Apps
#
# Resource group : project-rg
# Location       : Read from resource-group tags
# Environment    : Read from resource-group tags
# Registry       : Read from resource-group tags
#
# Prerequisites:
#   1. scripts/env-setup.sh
#   2. scripts/create-acr.sh
#   3. scripts/build-images.sh
#   4. scripts/deploy-azure-env.sh
#
# WARNING:
#   This script creates and modifies Azure resources.
#   It does not configure database persistence, application
#   secrets, database initialization, or application health.
# ============================================================

set -o pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-project-rg}"
EXPECTED_SUBSCRIPTION_ID="${EXPECTED_SUBSCRIPTION_ID:-4f004dab-3d26-4f85-bfd6-065fd3b81611}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
PLACEHOLDER_IMAGE="mcr.microsoft.com/k8se/quickstart:latest"

WAIT_SECONDS=8
MAX_RETRIES=5

trap 'echo "ERROR: Deployment failed near line ${LINENO}. Review the error above." >&2' ERR

log() {
    printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$*"
}

die() {
    echo "ERROR: $*" >&2
    exit 1
}

retry_az() {
    local attempt=1
    local delay="$WAIT_SECONDS"

    while (( attempt <= MAX_RETRIES )); do
        if "$@"; then
            return 0
        fi

        if (( attempt == MAX_RETRIES )); then
            echo "ERROR: Command failed after ${MAX_RETRIES} attempts." >&2
            return 1
        fi

        echo "Azure command failed (attempt ${attempt}/${MAX_RETRIES})."
        echo "Retrying in ${delay} seconds..."
        sleep "$delay"

        attempt=$((attempt + 1))
        delay=$((delay * 2))
    done

    return 1
}

# ------------------------------------------------------------
# 1. Verify Azure CLI, login and subscription
# ------------------------------------------------------------

log "Checking prerequisites..."

command -v az >/dev/null 2>&1 ||
    die "Azure CLI is not installed or not on PATH."

if ! az account show --output none 2>/dev/null; then
    die "Not logged in to Azure. Run: az login"
fi

CURRENT_SUBSCRIPTION_ID="$(az account show --query id --output tsv)"

[[ "$CURRENT_SUBSCRIPTION_ID" == "$EXPECTED_SUBSCRIPTION_ID" ]] ||
    die "Wrong subscription. Expected $EXPECTED_SUBSCRIPTION_ID; current $CURRENT_SUBSCRIPTION_ID."

log "Azure subscription verified: $CURRENT_SUBSCRIPTION_ID"

# ------------------------------------------------------------
# 2. Read configuration from resource-group tags
# ------------------------------------------------------------

log "Checking resource group..."

az group show --name "$RESOURCE_GROUP" --output none ||
    die "Resource group '$RESOURCE_GROUP' does not exist."

LOCATION="$(az group show \
    --name "$RESOURCE_GROUP" \
    --query "tags.location" \
    --output tsv)"

ENV_NAME="$(az group show \
    --name "$RESOURCE_GROUP" \
    --query "tags.envName" \
    --output tsv)"

REGISTRY_NAME="$(az group show \
    --name "$RESOURCE_GROUP" \
    --query "tags.registryName" \
    --output tsv)"

[[ -n "$LOCATION" && "$LOCATION" != "None" ]] ||
    die "The resource group's location tag is missing."

[[ -n "$ENV_NAME" && "$ENV_NAME" != "None" ]] ||
    die "The resource group's envName tag is missing."

[[ -n "$REGISTRY_NAME" && "$REGISTRY_NAME" != "None" ]] ||
    die "The resource group's registryName tag is missing."

REGISTRY_SERVER="${REGISTRY_NAME}.azurecr.io"

echo "Resource group : $RESOURCE_GROUP"
echo "Location       : $LOCATION"
echo "Environment    : $ENV_NAME"
echo "Registry       : $REGISTRY_NAME"
echo "Image tag      : $IMAGE_TAG"

# ------------------------------------------------------------
# 3. Verify environment and registry
# ------------------------------------------------------------

log "Checking Container Apps environment..."

az containerapp env show \
    --name "$ENV_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --output none ||
    die "Container Apps environment '$ENV_NAME' does not exist. Run scripts/deploy-azure-env.sh first."

log "Checking Azure Container Registry..."

az acr show \
    --name "$REGISTRY_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --output none ||
    die "Registry '$REGISTRY_NAME' does not exist."

ACR_ID="$(az acr show \
    --name "$REGISTRY_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query id \
    --output tsv)"

[[ -n "$ACR_ID" && "$ACR_ID" != "None" && "$ACR_ID" != "null" ]] ||
    die "Could not retrieve the ACR resource ID."

# ------------------------------------------------------------
# 4. Define the 18 applications
#
# Format:
# name|image|port|cpu|memory|min-replicas|max-replicas|ingress
#
# ingress:
# external = publicly reachable endpoint
# internal = reachable inside the Container Apps environment
# none     = ingress disabled
#
# Review ports, resource allocations, and exposure settings
# against each application's actual configuration.
# ------------------------------------------------------------

APPS=(
    "project-user-db|user-database|5003|0.25|0.5Gi|1|1|none"
    "project-assessment-db|assessment-database|5008|0.25|0.5Gi|1|1|none"
    "project-calendar-db|calendar-database|5006|0.25|0.5Gi|1|1|none"
    "project-enrolment-db|enrolment-database|5002|0.25|0.5Gi|1|1|none"
    "project-notebook-db|notebook-database|5004|0.25|0.5Gi|1|1|none"
    "project-exam-db|exam-database|5010|0.25|0.5Gi|1|1|none"

    "project-auth|auth-backend|5000|0.5|1Gi|0|2|external"
    "project-assessment-api|assessment-backend|5007|0.5|1Gi|0|2|external"
    "project-calendar-api|calendar-backend|5005|0.5|1Gi|0|2|external"
    "project-enrolment-api|enrolment-backend|5001|0.5|1Gi|0|2|external"
    "project-notebook-api|notebook-backend|5003|0.5|1Gi|0|2|external"
    "project-exam-api|exam-backend|5009|0.5|1Gi|0|2|external"

    "project-assessment-frontend|assessment-frontend|80|0.25|0.5Gi|0|2|external"
    "project-calendar-frontend|calendar-frontend|80|0.25|0.5Gi|0|2|external"
    "project-enrolment-frontend|enrolment-frontend|80|0.25|0.5Gi|0|2|external"
    "project-notebook-frontend|notebook-frontend|80|0.25|0.5Gi|0|2|external"
    "project-exam-frontend|exam-frontend|80|0.25|0.5Gi|0|2|external"
    "project-portal|portal-frontend|80|0.25|0.5Gi|0|2|external"
)

# ------------------------------------------------------------
# 5. Verify all image tags BEFORE changing apps
# ------------------------------------------------------------

log "Verifying all 18 images in ACR..."

for entry in "${APPS[@]}"; do
    IFS='|' read -r app image port cpu memory minrep maxrep ingress \
        <<< "$entry"

    if ! az acr repository show \
        --name "$REGISTRY_NAME" \
        --image "${image}:${IMAGE_TAG}" \
        --output none 2>/dev/null; then
        die "Image ${REGISTRY_SERVER}/${image}:${IMAGE_TAG} is missing. Build and push images first."
    fi

    echo "OK: ${image}:${IMAGE_TAG}"
done

log "All required image tags are present."

# ------------------------------------------------------------
# 6. Create missing apps and assign system identities
# ------------------------------------------------------------

log "Creating missing apps and checking identities..."

for entry in "${APPS[@]}"; do
    IFS='|' read -r app image port cpu memory minrep maxrep ingress \
        <<< "$entry"

    log "Checking app: $app"

    if ! az containerapp show \
        --name "$app" \
        --resource-group "$RESOURCE_GROUP" \
        --output none 2>/dev/null; then

        log "Creating $app with a temporary placeholder image..."

        if [[ "$ingress" == "none" ]]; then
            retry_az az containerapp create \
                --name "$app" \
                --resource-group "$RESOURCE_GROUP" \
                --environment "$ENV_NAME" \
                --image "$PLACEHOLDER_IMAGE" \
                --cpu "$cpu" \
                --memory "$memory" \
                --min-replicas "$minrep" \
                --max-replicas "$maxrep" \
                --ingress disabled \
                --output none
        else
            retry_az az containerapp create \
                --name "$app" \
                --resource-group "$RESOURCE_GROUP" \
                --environment "$ENV_NAME" \
                --image "$PLACEHOLDER_IMAGE" \
                --cpu "$cpu" \
                --memory "$memory" \
                --min-replicas "$minrep" \
                --max-replicas "$maxrep" \
                --ingress "$ingress" \
                --target-port "$port" \
                --output none
        fi
    else
        echo "Reusing existing app: $app"
    fi

    PRINCIPAL_ID="$(az containerapp show \
        --name "$app" \
        --resource-group "$RESOURCE_GROUP" \
        --query identity.principalId \
        --output tsv)"

    if [[ -z "$PRINCIPAL_ID" || "$PRINCIPAL_ID" == "None" || "$PRINCIPAL_ID" == "null" ]]; then
        log "Assigning system identity to $app..."

        retry_az az containerapp identity assign \
            --name "$app" \
            --resource-group "$RESOURCE_GROUP" \
            --system-assigned \
            --output none

        PRINCIPAL_ID="$(az containerapp show \
            --name "$app" \
            --resource-group "$RESOURCE_GROUP" \
            --query identity.principalId \
            --output tsv)"

        [[ -n "$PRINCIPAL_ID" && "$PRINCIPAL_ID" != "None" && "$PRINCIPAL_ID" != "null" ]] ||
            die "Could not obtain managed identity for $app."
    fi

    echo "Managed identity ready: $app"
done

# ------------------------------------------------------------
# 7. Grant AcrPull to each managed identity
# ------------------------------------------------------------

log "Configuring ACR pull permissions..."

for entry in "${APPS[@]}"; do
    IFS='|' read -r app image port cpu memory minrep maxrep ingress \
        <<< "$entry"

    PRINCIPAL_ID="$(az containerapp show \
        --name "$app" \
        --resource-group "$RESOURCE_GROUP" \
        --query identity.principalId \
        --output tsv)"

    [[ -n "$PRINCIPAL_ID" && "$PRINCIPAL_ID" != "None" && "$PRINCIPAL_ID" != "null" ]] ||
        die "No managed identity found for $app."

    ASSIGNMENT_ID="$(az role assignment list \
        --scope "$ACR_ID" \
        --query "[?principalId=='${PRINCIPAL_ID}' && roleDefinitionName=='AcrPull'].id | [0]" \
        --output tsv)"

    if [[ -z "$ASSIGNMENT_ID" || "$ASSIGNMENT_ID" == "None" || "$ASSIGNMENT_ID" == "null" ]]; then
        log "Granting AcrPull to $app..."

        retry_az az role assignment create \
            --assignee-object-id "$PRINCIPAL_ID" \
            --assignee-principal-type ServicePrincipal \
            --role AcrPull \
            --scope "$ACR_ID" \
            --output none
    else
        echo "AcrPull already assigned: $app"
    fi
done

# ------------------------------------------------------------
# 8. Configure managed-identity registry authentication
# ------------------------------------------------------------

log "Configuring ACR authentication for each app..."

for entry in "${APPS[@]}"; do
    IFS='|' read -r app image port cpu memory minrep maxrep ingress \
        <<< "$entry"

    retry_az az containerapp registry set \
        --name "$app" \
        --resource-group "$RESOURCE_GROUP" \
        --server "$REGISTRY_SERVER" \
        --identity system \
        --output none

    echo "Registry authentication configured: $app"
done

log "Waiting for role assignments to propagate..."
sleep 30

# ------------------------------------------------------------
# 9. Deploy images and configure ingress
# ------------------------------------------------------------

log "Deploying application images..."

for entry in "${APPS[@]}"; do
    IFS='|' read -r app image port cpu memory minrep maxrep ingress \
        <<< "$entry"

    log "Updating $app to ${REGISTRY_SERVER}/${image}:${IMAGE_TAG}..."

    retry_az az containerapp update \
        --name "$app" \
        --resource-group "$RESOURCE_GROUP" \
        --image "${REGISTRY_SERVER}/${image}:${IMAGE_TAG}" \
        --cpu "$cpu" \
        --memory "$memory" \
        --min-replicas "$minrep" \
        --max-replicas "$maxrep" \
        --output none

    case "$ingress" in
        external|internal)
            retry_az az containerapp ingress enable \
                --name "$app" \
                --resource-group "$RESOURCE_GROUP" \
                --type "$ingress" \
                --target-port "$port" \
                --transport auto \
                --output none
            ;;
        none)
            # Explicitly disable ingress on database apps,
            # including apps that already existed.
            if az containerapp show \
                --name "$app" \
                --resource-group "$RESOURCE_GROUP" \
                --query "properties.configuration.ingress.external" \
                --output tsv 2>/dev/null | grep -qi '^true$'; then

                log "Disabling external ingress for $app..."

                retry_az az containerapp ingress disable \
                    --name "$app" \
                    --resource-group "$RESOURCE_GROUP" \
                    --output none
            else
                echo "No external ingress detected for $app."
            fi
            ;;
        *)
            die "Unknown ingress setting '$ingress' for $app."
            ;;
    esac

    echo "Updated: $app"
done

# ------------------------------------------------------------
# 10. Display app states and endpoints
# ------------------------------------------------------------

log "Deployment commands completed. Checking app status..."

for entry in "${APPS[@]}"; do
    IFS='|' read -r app image port cpu memory minrep maxrep ingress \
        <<< "$entry"

    STATE="$(az containerapp show \
        --name "$app" \
        --resource-group "$RESOURCE_GROUP" \
        --query properties.provisioningState \
        --output tsv 2>/dev/null || echo "Unknown")"

    FQDN="$(az containerapp show \
        --name "$app" \
        --resource-group "$RESOURCE_GROUP" \
        --query properties.configuration.ingress.fqdn \
        --output tsv 2>/dev/null || true)"

    printf '%-32s state=%-15s' "$app" "$STATE"

    if [[ -n "$FQDN" && "$FQDN" != "None" && "$FQDN" != "null" ]]; then
        printf ' URL=https://%s' "$FQDN"
    fi

    printf '\n'
done

log "Deployment script finished."
echo "A successful command does not guarantee that every app is healthy."
echo "Check application logs, database connectivity, secrets, and persistence."
echo "Run scripts/deployment-testing.sh after reviewing the deployed apps."
