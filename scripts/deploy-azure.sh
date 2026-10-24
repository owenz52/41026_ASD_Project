#!/usr/bin/env bash
set -Eeuo pipefail

# Git Bash / MSYS2 rewrites arguments that start with "/" (such as
# /subscriptions/...) into Windows paths before az sees them, which
# silently breaks --scope and similar options. Disable that.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'

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
#   5. scripts/preflight-check.sh   (recommended)
#
# Changes from the previous version:
#   - Database apps use INTERNAL ingress (reachable by your APIs
#     inside the environment, not from the internet). Apps with
#     no ingress cannot receive any traffic, even internal.
#   - Removed the invalid "--ingress disabled" flag from create.
#   - Every update creates a new revision (--revision-suffix), so
#     re-running with IMAGE_TAG=latest really pulls the new image.
#   - Placeholder apps use port 80 (what the quickstart image uses).
#   - System identity is assigned at creation time.
#   - ACR image errors are shown instead of hidden.
#   - Final status check fails the script if any app is not healthy.
#   - project-auth keeps 1 replica warm to avoid cold-start logins.
#
# Optional environment variables:
#   RESOURCE_GROUP, EXPECTED_SUBSCRIPTION_ID, IMAGE_TAG
#   ACR_AUTH       identity (default) or admin.
#                  identity = managed identity + AcrPull role (needs
#                             Owner / User Access Administrator on the
#                             registry to create the role assignments).
#                  admin    = registry admin username/password. Works
#                             with Contributor only. Less secure: the
#                             password is stored as a secret in each app.
#   DB_TRANSPORT   auto (HTTP, default) or tcp. Use tcp only if the
#                  database apps speak a raw TCP protocol rather than
#                  HTTP (e.g. a real Postgres/MySQL server).
#
# WARNING:
#   This script creates and modifies Azure resources.
#   It does not configure application environment variables,
#   secrets, database persistence, or database initialization.
# ============================================================

RESOURCE_GROUP="${RESOURCE_GROUP:-project-rg}"
EXPECTED_SUBSCRIPTION_ID="${EXPECTED_SUBSCRIPTION_ID:-4f004dab-3d26-4f85-bfd6-065fd3b81611}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
DB_TRANSPORT="${DB_TRANSPORT:-auto}"
ACR_AUTH="${ACR_AUTH:-identity}"

PLACEHOLDER_IMAGE="mcr.microsoft.com/k8se/quickstart:latest"
PLACEHOLDER_PORT=80
REVISION_SUFFIX="r$(date +%s)"

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

nullish() {
    [[ -z "${1:-}" || "$1" == "None" || "$1" == "null" ]]
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

[[ "$ACR_AUTH" == "identity" || "$ACR_AUTH" == "admin" ]] ||
    die "ACR_AUTH must be 'identity' or 'admin' (got '$ACR_AUTH')."

[[ "$DB_TRANSPORT" == "auto" || "$DB_TRANSPORT" == "tcp" ]] ||
    die "DB_TRANSPORT must be 'auto' or 'tcp' (got '$DB_TRANSPORT')."

# ------------------------------------------------------------
# 1. Verify Azure CLI, login and subscription
# ------------------------------------------------------------

log "Checking prerequisites..."

command -v az >/dev/null 2>&1 ||
    die "Azure CLI is not installed or not on PATH."

# Some Azure CLI installs (Git Bash/Windows, some wrappers) emit CRLF line
# endings, which silently corrupts values read with $(...) or read.
# Strip carriage returns from everything az prints. Defined AFTER the
# "az is installed" check so that check still works.
az() { command az "$@" | tr -d '\r'; }

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

nullish "$LOCATION"      && die "The resource group's location tag is missing."
nullish "$ENV_NAME"      && die "The resource group's envName tag is missing."
nullish "$REGISTRY_NAME" && die "The resource group's registryName tag is missing."

REGISTRY_SERVER="${REGISTRY_NAME}.azurecr.io"

echo "Resource group : $RESOURCE_GROUP"
echo "Location       : $LOCATION"
echo "Environment    : $ENV_NAME"
echo "Registry       : $REGISTRY_NAME"
echo "Image tag      : $IMAGE_TAG"
echo "Revision suffix: $REVISION_SUFFIX"
echo "DB transport   : $DB_TRANSPORT"
echo "ACR auth        : $ACR_AUTH"

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

nullish "$ACR_ID" && die "Could not retrieve the ACR resource ID."

# ------------------------------------------------------------
# 4. Define the 18 applications
#
# Format:
# name|image|port|cpu|memory|min-replicas|max-replicas|ingress
#
# ingress:
# external = publicly reachable endpoint
# internal = reachable only inside the Container Apps environment
# none     = ingress disabled (the app can receive NO traffic;
#            only use for background workers)
#
# Databases are "internal" so the APIs can reach them by name:
#   http://project-user-db   (HTTP, port 80)
# For DB_TRANSPORT=tcp use project-user-db:<port> instead.
#
# NOTE: project-user-db and project-notebook-api both use 5003.
# That does not clash (different apps), but every other port is
# unique, so double-check user-db's port is really 5003.
# ------------------------------------------------------------

APPS=(
    "project-user-db|user-database|5003|0.25|0.5Gi|1|1|internal"
    "project-assessment-db|assessment-database|5008|0.25|0.5Gi|1|1|internal"
    "project-calendar-db|calendar-database|5006|0.25|0.5Gi|1|1|internal"
    "project-enrolment-db|enrolment-database|5002|0.25|0.5Gi|1|1|internal"
    "project-notebook-db|notebook-database|5004|0.25|0.5Gi|1|1|internal"
    "project-exam-db|exam-database|5010|0.25|0.5Gi|1|1|internal"

    "project-auth|auth-backend|5000|0.5|1Gi|1|2|external"
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

log "Verifying all ${#APPS[@]} images in ACR..."

for entry in "${APPS[@]}"; do
    IFS='|' read -r app image port cpu memory minrep maxrep ingress \
        <<< "$entry"

    if ! ACR_OUTPUT="$(az acr repository show \
        --name "$REGISTRY_NAME" \
        --image "${image}:${IMAGE_TAG}" \
        --output none 2>&1)"; then
        echo "$ACR_OUTPUT" >&2
        die "Image ${REGISTRY_SERVER}/${image}:${IMAGE_TAG} could not be verified. Build and push images first, or check your ACR permissions."
    fi

    echo "OK: ${image}:${IMAGE_TAG}"
done

log "All required image tags are present."

# ------------------------------------------------------------
# 6. Create missing apps (with a system identity)
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

        create_args=(
            --name "$app"
            --resource-group "$RESOURCE_GROUP"
            --environment "$ENV_NAME"
            --image "$PLACEHOLDER_IMAGE"
            --cpu "$cpu"
            --memory "$memory"
            --min-replicas "$minrep"
            --max-replicas "$maxrep"
            --system-assigned
            --output none
        )

        # The placeholder listens on port 80. The real port is applied
        # in step 9 when the real image is deployed.
        if [[ "$ingress" != "none" ]]; then
            create_args+=(--ingress "$ingress" --target-port "$PLACEHOLDER_PORT")
        fi

        retry_az az containerapp create "${create_args[@]}"
    else
        echo "Reusing existing app: $app"
    fi

    PRINCIPAL_ID="$(az containerapp show \
        --name "$app" \
        --resource-group "$RESOURCE_GROUP" \
        --query identity.principalId \
        --output tsv)"

    if nullish "$PRINCIPAL_ID"; then
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

        nullish "$PRINCIPAL_ID" && die "Could not obtain managed identity for $app."
    fi

    echo "Managed identity ready: $app"
done

# ------------------------------------------------------------
# 7. Grant AcrPull to each managed identity
# ------------------------------------------------------------

if [[ "$ACR_AUTH" == "identity" ]]; then
log "Configuring ACR pull permissions..."

for entry in "${APPS[@]}"; do
    IFS='|' read -r app image port cpu memory minrep maxrep ingress \
        <<< "$entry"

    PRINCIPAL_ID="$(az containerapp show \
        --name "$app" \
        --resource-group "$RESOURCE_GROUP" \
        --query identity.principalId \
        --output tsv)"

    nullish "$PRINCIPAL_ID" && die "No managed identity found for $app."

    ASSIGNMENT_ID="$(az role assignment list \
        --scope "$ACR_ID" \
        --query "[?principalId=='${PRINCIPAL_ID}' && roleDefinitionName=='AcrPull'].id | [0]" \
        --output tsv)"

    if nullish "$ASSIGNMENT_ID"; then
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
else
    log "ACR_AUTH=admin: skipping AcrPull role assignments."
fi

# ------------------------------------------------------------
# 8. Configure managed-identity registry authentication
# ------------------------------------------------------------

log "Configuring ACR authentication for each app..."

ACR_USER=""
ACR_PASS=""

if [[ "$ACR_AUTH" == "admin" ]]; then
    log "Enabling ACR admin user and reading credentials..."

    retry_az az acr update \
        --name "$REGISTRY_NAME" \
        --admin-enabled true \
        --output none

    ACR_USER="$(az acr credential show \
        --name "$REGISTRY_NAME" \
        --query username \
        --output tsv)"

    ACR_PASS="$(az acr credential show \
        --name "$REGISTRY_NAME" \
        --query "passwords[0].value" \
        --output tsv)"

    nullish "$ACR_USER" && die "Could not read ACR admin username. Admin user may be blocked by policy."
    nullish "$ACR_PASS" && die "Could not read ACR admin password."
fi

for entry in "${APPS[@]}"; do
    IFS='|' read -r app image port cpu memory minrep maxrep ingress \
        <<< "$entry"

    if [[ "$ACR_AUTH" == "admin" ]]; then
        retry_az az containerapp registry set \
            --name "$app" \
            --resource-group "$RESOURCE_GROUP" \
            --server "$REGISTRY_SERVER" \
            --username "$ACR_USER" \
            --password "$ACR_PASS" \
            --output none
    else
        retry_az az containerapp registry set \
            --name "$app" \
            --resource-group "$RESOURCE_GROUP" \
            --server "$REGISTRY_SERVER" \
            --identity system \
            --output none
    fi

    echo "Registry authentication configured: $app"
done

if [[ "$ACR_AUTH" == "identity" ]]; then
    log "Waiting for role assignments to propagate..."
    sleep 30
fi

# ------------------------------------------------------------
# 9. Deploy only apps whose desired configuration has changed
#
# An app is skipped when its image reference, CPU, memory, scale,
# ingress type, target port, and transport already match. This avoids
# creating a new revision on every rerun.
#
# Note: comparing image references cannot detect that a mutable tag
# such as :latest was overwritten with different image content. Use
# immutable tags (for example, a Git commit SHA) to detect image changes.
# ------------------------------------------------------------

app_matches_desired_config() {
    local app="$1" image="$2" port="$3" cpu="$4" memory="$5"
    local minrep="$6" maxrep="$7" ingress="$8"
    local desired_image current_image current_cpu current_memory
    local current_min current_max current_external current_port
    local current_transport current_exposed desired_external desired_transport

    desired_image="${REGISTRY_SERVER}/${image}:${IMAGE_TAG}"

    # Any failed query is treated as a mismatch so deployment can proceed
    # and Azure's real error is surfaced by the subsequent update command.
    current_image="$(az containerapp show --name "$app" --resource-group "$RESOURCE_GROUP" --query 'properties.template.containers[0].image' --output tsv 2>/dev/null || true)"
    current_cpu="$(az containerapp show --name "$app" --resource-group "$RESOURCE_GROUP" --query 'properties.template.containers[0].resources.cpu' --output tsv 2>/dev/null || true)"
    current_memory="$(az containerapp show --name "$app" --resource-group "$RESOURCE_GROUP" --query 'properties.template.containers[0].resources.memory' --output tsv 2>/dev/null || true)"
    current_min="$(az containerapp show --name "$app" --resource-group "$RESOURCE_GROUP" --query 'properties.template.scale.minReplicas' --output tsv 2>/dev/null || true)"
    current_max="$(az containerapp show --name "$app" --resource-group "$RESOURCE_GROUP" --query 'properties.template.scale.maxReplicas' --output tsv 2>/dev/null || true)"
    current_external="$(az containerapp show --name "$app" --resource-group "$RESOURCE_GROUP" --query 'properties.configuration.ingress.external' --output tsv 2>/dev/null || true)"
    current_port="$(az containerapp show --name "$app" --resource-group "$RESOURCE_GROUP" --query 'properties.configuration.ingress.targetPort' --output tsv 2>/dev/null || true)"
    current_transport="$(az containerapp show --name "$app" --resource-group "$RESOURCE_GROUP" --query 'properties.configuration.ingress.transport' --output tsv 2>/dev/null || true)"
    current_exposed="$(az containerapp show --name "$app" --resource-group "$RESOURCE_GROUP" --query 'properties.configuration.ingress.exposedPort' --output tsv 2>/dev/null || true)"

    case "$ingress" in
        external) desired_external="true" ;;
        internal) desired_external="false" ;;
        none)
            # This app definition requests ingress disabled. Azure's null
            # ingress properties indicate no ingress configuration.
            [[ "$current_port" == "None" || "$current_port" == "null" || -z "$current_port" ]] || return 1
            ;;
        *) return 1 ;;
    esac

    if [[ "$ingress" != "none" ]]; then
        if [[ "$app" == *-db && "$DB_TRANSPORT" == "tcp" ]]; then
            desired_transport="tcp"
        else
            desired_transport="auto"
        fi

        [[ "$current_external" == "$desired_external" ]] || return 1
        [[ "$current_port" == "$port" ]] || return 1
        [[ "$current_transport" == "$desired_transport" ]] || return 1

        if [[ "$desired_transport" == "tcp" ]]; then
            [[ "$current_exposed" == "$port" ]] || return 1
        fi
    fi

    [[ "$current_image" == "$desired_image" ]] || return 1
    [[ "$current_cpu" == "$cpu" ]] || return 1
    [[ "$current_memory" == "$memory" ]] || return 1
    [[ "$current_min" == "$minrep" ]] || return 1
    [[ "$current_max" == "$maxrep" ]] || return 1

    return 0
}

configure_ingress() {
    local app="$1" ingress="$2" port="$3"
    local current_fqdn
    local transport_args=(--transport auto)

    current_fqdn="$(az containerapp show \
        --name "$app" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.configuration.ingress.fqdn" \
        --output tsv 2>/dev/null || true)"

    case "$ingress" in
        external|internal)
            if [[ "$app" == *-db && "$DB_TRANSPORT" == "tcp" ]]; then
                transport_args=(--transport tcp --exposed-port "$port")
            fi

            if nullish "$current_fqdn"; then
                retry_az az containerapp ingress enable \
                    --name "$app" \
                    --resource-group "$RESOURCE_GROUP" \
                    --type "$ingress" \
                    --target-port "$port" \
                    "${transport_args[@]}" \
                    --output none
            else
                retry_az az containerapp ingress update \
                    --name "$app" \
                    --resource-group "$RESOURCE_GROUP" \
                    --type "$ingress" \
                    --target-port "$port" \
                    "${transport_args[@]}" \
                    --output none
            fi
            ;;
        none)
            if ! nullish "$current_fqdn"; then
                log "Disabling ingress for $app..."
                retry_az az containerapp ingress disable \
                    --name "$app" \
                    --resource-group "$RESOURCE_GROUP" \
                    --output none
            else
                echo "No ingress configured for $app."
            fi
            ;;
        *)
            die "Unknown ingress setting '$ingress' for $app."
            ;;
    esac
}

log "Deploying application images..."

for entry in "${APPS[@]}"; do
    IFS='|' read -r app image port cpu memory minrep maxrep ingress \
        <<< "$entry"

    if app_matches_desired_config "$app" "$image" "$port" "$cpu" "$memory" "$minrep" "$maxrep" "$ingress"; then
        echo "SKIP: $app already matches the desired image and configuration."
        continue
    fi

    log "Configuration differs for $app; deploying desired state..."
    log "Configuring ingress for $app ($ingress, port $port)..."
    configure_ingress "$app" "$ingress" "$port"

    log "Updating $app to ${REGISTRY_SERVER}/${image}:${IMAGE_TAG}..."

    retry_az az containerapp update \
        --name "$app" \
        --resource-group "$RESOURCE_GROUP" \
        --image "${REGISTRY_SERVER}/${image}:${IMAGE_TAG}" \
        --cpu "$cpu" \
        --memory "$memory" \
        --min-replicas "$minrep" \
        --max-replicas "$maxrep" \
        --revision-suffix "$REVISION_SUFFIX" \
        --output none

    echo "Updated: $app"
done

# ------------------------------------------------------------
# 10. Display app states and endpoints
# ------------------------------------------------------------

log "Deployment commands completed. Checking app status..."

UNHEALTHY=0

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

    [[ "$STATE" == "Succeeded" ]] || UNHEALTHY=$((UNHEALTHY + 1))

    printf '%-32s state=%-12s' "$app" "$STATE"

    if ! nullish "$FQDN"; then
        if [[ "$ingress" == "external" ]]; then
            printf ' URL=https://%s' "$FQDN"
        else
            printf ' internal=%s' "$FQDN"
        fi
    fi

    printf '\n'
done

log "Deployment script finished."

if (( UNHEALTHY > 0 )); then
    echo "WARNING: $UNHEALTHY app(s) are not in the Succeeded state." >&2
    echo "Check logs: az containerapp logs show -n <app> -g $RESOURCE_GROUP --type console --tail 100" >&2
    exit 1
fi

echo "A Succeeded state does not guarantee that every app is healthy."
echo "Check application logs, database connectivity, secrets, and persistence."
echo "Run scripts/deployment-testing.sh next."