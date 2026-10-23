#!/usr/bin/env bash
set -Euo pipefail

# Git Bash / MSYS2 rewrites arguments that start with "/" (such as
# /subscriptions/...) into Windows paths before az sees them, which
# silently breaks --scope and similar options. Disable that.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'

# ============================================================
# Pre-flight check for the 18-service Container Apps deployment
#
# Read-only. Creates and modifies NOTHING. Run it before the
# real deployment script; if it exits 0, the deploy should not
# trip over the usual avoidable errors.
#
# Checks:
#   1. Tools, login, subscription, resource providers
#   2. Resource-group tags (location, envName, registryName)
#   3. Container Apps environment and ACR state
#   4. Your permission to create role assignments (AcrPull)
#   5. The APPS table itself (names, ports, CPU/memory, ingress)
#   6. All 18 images + tag exist in ACR
#   7. Current state of any apps that already exist
#   8. Planned vCPU / memory totals
#
# Exit code: 0 = ready to deploy (warnings allowed),
#            1 = fix errors first.
# ============================================================

RESOURCE_GROUP="${RESOURCE_GROUP:-project-rg}"
ACR_AUTH="${ACR_AUTH:-identity}"   # identity | admin (match your deploy run)
EXPECTED_SUBSCRIPTION_ID="${EXPECTED_SUBSCRIPTION_ID:-4f004dab-3d26-4f85-bfd6-065fd3b81611}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

ERRORS=0
WARNINGS=0

section() { printf '\n== %s ==\n' "$*"; }
ok()      { printf '  [ OK ] %s\n' "$*"; }
warn()    { printf '  [WARN] %s\n' "$*"; WARNINGS=$((WARNINGS + 1)); }
err()     { printf '  [FAIL] %s\n' "$*"; ERRORS=$((ERRORS + 1)); }
nullish() { [[ -z "${1:-}" || "$1" == "null" || "$1" == "None" ]]; }

# ------------------------------------------------------------
# App table (keep in sync with the deploy script)
# Format: name|image|port|cpu|memory|min-replicas|max-replicas|ingress
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

EXPECTED_APP_COUNT=18

# ------------------------------------------------------------
# 1. Tools, login, subscription, providers
# ------------------------------------------------------------

section "Tools and login"

if command -v az >/dev/null 2>&1; then
    ok "Azure CLI found"
else
    err "Azure CLI is not installed or not on PATH"
    echo; echo "Cannot continue without Azure CLI."; exit 1
fi

# Some Azure CLI installs (Git Bash/Windows, some wrappers) emit CRLF line
# endings, which silently corrupts values read with $(...) or read.
# Strip carriage returns from everything az prints. Defined AFTER the
# "az is installed" check so that check still works.
az() { command az "$@" | tr -d '\r'; }

if ! az account show --output none 2>/dev/null; then
    err "Not logged in. Run: az login"
    echo; echo "Cannot continue without a login."; exit 1
fi
ok "Logged in to Azure"

CURRENT_SUB="$(az account show --query id --output tsv)"
if [[ "$CURRENT_SUB" == "$EXPECTED_SUBSCRIPTION_ID" ]]; then
    ok "Correct subscription ($CURRENT_SUB)"
else
    err "Wrong subscription. Expected $EXPECTED_SUBSCRIPTION_ID; current $CURRENT_SUB"
    echo; echo "Cannot continue on the wrong subscription."; exit 1
fi

if az containerapp --help >/dev/null 2>&1; then
    ok "'az containerapp' commands available"
else
    err "'az containerapp' not available. Run: az extension add --name containerapp --upgrade"
fi

for provider in Microsoft.App Microsoft.OperationalInsights Microsoft.ContainerRegistry; do
    state="$(az provider show --namespace "$provider" --query registrationState --output tsv 2>/dev/null || true)"
    if [[ "$state" == "Registered" ]]; then
        ok "Provider $provider registered"
    else
        err "Provider $provider is '${state:-unknown}'. Run: az provider register --namespace $provider"
    fi
done

# ------------------------------------------------------------
# 2. Resource group and tags
# ------------------------------------------------------------

section "Resource group and tags"

if ! az group show --name "$RESOURCE_GROUP" --output none 2>/dev/null; then
    err "Resource group '$RESOURCE_GROUP' does not exist"
    echo; echo "Cannot continue without the resource group."; exit 1
fi
ok "Resource group '$RESOURCE_GROUP' exists"

LOCATION="$(az group show --name "$RESOURCE_GROUP" --query "tags.location" --output tsv 2>/dev/null || true)"
ENV_NAME="$(az group show --name "$RESOURCE_GROUP" --query "tags.envName" --output tsv 2>/dev/null || true)"
REGISTRY_NAME="$(az group show --name "$RESOURCE_GROUP" --query "tags.registryName" --output tsv 2>/dev/null || true)"

nullish "$LOCATION"      && err "Tag 'location' is missing"     || ok "location     = $LOCATION"
nullish "$ENV_NAME"      && err "Tag 'envName' is missing"      || ok "envName      = $ENV_NAME"
nullish "$REGISTRY_NAME" && err "Tag 'registryName' is missing" || ok "registryName = $REGISTRY_NAME"

if nullish "$ENV_NAME" || nullish "$REGISTRY_NAME"; then
    echo; echo "Cannot check the environment or registry without their tags."
    echo "Errors: $ERRORS"; exit 1
fi

REGISTRY_SERVER="${REGISTRY_NAME}.azurecr.io"

# ------------------------------------------------------------
# 3. Environment and registry
# ------------------------------------------------------------

section "Container Apps environment"

ENV_STATE="$(az containerapp env show \
    --name "$ENV_NAME" --resource-group "$RESOURCE_GROUP" \
    --query properties.provisioningState --output tsv 2>/dev/null || true)"

if [[ "$ENV_STATE" == "Succeeded" ]]; then
    ok "Environment '$ENV_NAME' is Succeeded"
elif [[ -z "$ENV_STATE" ]]; then
    err "Environment '$ENV_NAME' does not exist. Run scripts/deploy-azure-env.sh first"
else
    err "Environment '$ENV_NAME' is in state '$ENV_STATE' (expected Succeeded)"
    echo "         Diagnose with:"
    echo "           az containerapp env show -n $ENV_NAME -g $RESOURCE_GROUP --query properties -o jsonc"
    echo "           az monitor activity-log list -g $RESOURCE_GROUP --offset 2d \\"
    echo "             --query \"[?status.value=='Failed'].{op:operationName.localizedValue,msg:properties.statusMessage}\" -o json"
fi

section "Container registry"

ACR_ID=""
ACR_FIELDS="$(az acr show \
    --name "$REGISTRY_NAME" --resource-group "$RESOURCE_GROUP" \
    --query "[id, to_string(provisioningState), to_string(publicNetworkAccess), sku.name]" \
    --output tsv 2>/dev/null | tr '\n' ' ' || true)"

if [[ -z "${ACR_FIELDS// /}" ]]; then
    err "Registry '$REGISTRY_NAME' does not exist in '$RESOURCE_GROUP'"
else
    read -r ACR_ID ACR_STATE ACR_PUBLIC ACR_SKU <<< "$ACR_FIELDS"
    ok "Registry '$REGISTRY_NAME' found (SKU: $ACR_SKU)"
    [[ "$ACR_STATE" == "Succeeded" ]] || err "Registry state is '$ACR_STATE' (expected Succeeded)"
    if [[ "$ACR_PUBLIC" == "Disabled" ]]; then
        warn "Registry public network access is Disabled; Container Apps may be unable to pull images"
    fi
fi

# ------------------------------------------------------------
# 4. Can this identity grant AcrPull?
# ------------------------------------------------------------

section "Permissions"

# Uses Azure's effective-permissions API for YOUR signed-in identity. Unlike
# listing role names, this correctly accounts for group-based roles,
# inherited roles, classic administrators and custom roles.
perm_count() {
    # $1 = resource id, $2 = JMESPath expression returning a number
    az rest --method get \
        --url "https://management.azure.com${1}/providers/Microsoft.Authorization/permissions?api-version=2022-04-01" \
        --query "$2" --output tsv 2>/dev/null || true
}

CAN_ASSIGN_FILTER="length(value[?(contains(actions,'*') || contains(actions,'Microsoft.Authorization/*') || contains(actions,'Microsoft.Authorization/roleAssignments/write')) && !contains(notActions,'Microsoft.Authorization/*') && !contains(notActions,'Microsoft.Authorization/*/Write') && !contains(notActions,'Microsoft.Authorization/roleAssignments/write')])"
CAN_MANAGE_FILTER="length(value[?contains(actions,'*')])"

if [[ -n "$ACR_ID" ]]; then
    N="$(perm_count "$ACR_ID" "$CAN_ASSIGN_FILTER")"

    if [[ ! "$N" =~ ^[0-9]+$ ]]; then
        warn "Could not read your effective permissions; verify manually that you can create role assignments on the registry"
    elif (( N > 0 )); then
        ok "You can create role assignments on the registry (needed for AcrPull)"
    elif [[ "$ACR_AUTH" == "admin" ]]; then
        ok "No role-assignment rights, but ACR_AUTH=admin does not need them"
    else
        err "Your effective permissions on the registry do not allow creating role assignments; granting AcrPull will fail"
        echo "         Either get Owner/User Access Administrator, or deploy with:  ACR_AUTH=admin ./scripts/deploy-azure-apps.sh"
    fi
else
    warn "Skipped registry permission check (registry not found)"
fi

RG_ID="/subscriptions/${CURRENT_SUB}/resourceGroups/${RESOURCE_GROUP}"
N="$(perm_count "$RG_ID" "$CAN_MANAGE_FILTER")"

if [[ ! "$N" =~ ^[0-9]+$ ]]; then
    warn "Could not read your effective permissions on the resource group"
elif (( N > 0 )); then
    ok "You can manage resources in the resource group"
else
    warn "No full-management role found on the resource group; creating apps may fail"
fi

# ------------------------------------------------------------
# 5. Validate the APPS table
# ------------------------------------------------------------

section "App definitions"

if (( ${#APPS[@]} == EXPECTED_APP_COUNT )); then
    ok "${#APPS[@]} apps defined"
else
    err "Expected $EXPECTED_APP_COUNT apps, found ${#APPS[@]}"
fi

declare -A SEEN_NAMES=()
TABLE_OK=1
TOTAL_CPU_MIN=0
TOTAL_CPU_MAX=0
TOTAL_MEM_MAX=0

for entry in "${APPS[@]}"; do
    IFS='|' read -r app image port cpu memory minrep maxrep ingress <<< "$entry"
    problems=()

    [[ -n "${SEEN_NAMES[$app]:-}" ]] && problems+=("duplicate app name")
    SEEN_NAMES[$app]=1

    [[ "$app" =~ ^[a-z]([a-z0-9-]*[a-z0-9])?$ ]] || problems+=("name must be lowercase letters, digits, hyphens")
    (( ${#app} <= 32 )) || problems+=("name longer than 32 characters")
    [[ "$app" != *--* ]] || problems+=("name contains '--'")

    [[ -n "$image" ]] || problems+=("image is empty")

    case "$ingress" in
        external|internal)
            [[ "$port" =~ ^[0-9]+$ ]] && (( port >= 1 && port <= 65535 )) || problems+=("invalid port '$port'") ;;
        none) ;;
        *) problems+=("unknown ingress '$ingress'") ;;
    esac

    [[ "$minrep" =~ ^[0-9]+$ && "$maxrep" =~ ^[0-9]+$ ]] || problems+=("replicas must be integers")
    if [[ "$minrep" =~ ^[0-9]+$ && "$maxrep" =~ ^[0-9]+$ ]]; then
        (( minrep <= maxrep )) || problems+=("min replicas ($minrep) > max ($maxrep)")
        (( maxrep >= 1 ))      || problems+=("max replicas must be at least 1")
    fi

    # Consumption plan: memory must be 2x CPU, and CPU must be a valid size
    mem_num="${memory%Gi}"
    if [[ "$memory" != *Gi || ! "$mem_num" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
        problems+=("memory '$memory' must look like 0.5Gi")
    elif ! awk -v c="$cpu" -v m="$mem_num" 'BEGIN { exit !(c * 2 == m) }'; then
        problems+=("CPU $cpu / memory $memory is not a valid Consumption pairing (memory should be 2x CPU)")
    fi
    awk -v c="$cpu" 'BEGIN { exit !(c >= 0.25 && c <= 4 && (c * 100) % 25 == 0) }' ||
        problems+=("CPU '$cpu' is not a valid Consumption size")

    if (( ${#problems[@]} > 0 )); then
        TABLE_OK=0
        for p in "${problems[@]}"; do err "$app: $p"; done
    else
        TOTAL_CPU_MIN="$(awk -v t="$TOTAL_CPU_MIN" -v c="$cpu" -v r="$minrep" 'BEGIN { print t + c * r }')"
        TOTAL_CPU_MAX="$(awk -v t="$TOTAL_CPU_MAX" -v c="$cpu" -v r="$maxrep" 'BEGIN { print t + c * r }')"
        TOTAL_MEM_MAX="$(awk -v t="$TOTAL_MEM_MAX" -v m="$mem_num" -v r="$maxrep" 'BEGIN { print t + m * r }')"
    fi
done

(( TABLE_OK == 1 )) && ok "All app definitions are valid"

# ------------------------------------------------------------
# 6. Images exist in ACR
# ------------------------------------------------------------

section "Images in ACR (tag: $IMAGE_TAG)"

if [[ -n "$ACR_ID" ]]; then
    for entry in "${APPS[@]}"; do
        IFS='|' read -r app image _ <<< "$entry"
        if az acr repository show \
            --name "$REGISTRY_NAME" --image "${image}:${IMAGE_TAG}" \
            --output none 2>/dev/null; then
            ok "${image}:${IMAGE_TAG}"
        else
            err "${REGISTRY_SERVER}/${image}:${IMAGE_TAG} is missing. Run scripts/build-images.sh"
        fi
    done
else
    warn "Skipped image checks (registry not found)"
fi

# ------------------------------------------------------------
# 7. Existing apps
# ------------------------------------------------------------

section "Existing apps"

EXISTING=0
NEW=0

if [[ "$ENV_STATE" == "Succeeded" ]]; then
    for entry in "${APPS[@]}"; do
        IFS='|' read -r app image port cpu memory minrep maxrep ingress <<< "$entry"

        FIELDS="$(az containerapp show \
            --name "$app" --resource-group "$RESOURCE_GROUP" \
            --query "[to_string(properties.provisioningState),
                      to_string(properties.managedEnvironmentId),
                      to_string(properties.configuration.ingress.external)]" \
            --output tsv 2>/dev/null | tr '\n' ' ' || true)"

        if [[ -z "${FIELDS// /}" ]]; then
            NEW=$((NEW + 1))
            continue
        fi

        EXISTING=$((EXISTING + 1))
        read -r STATE ENV_ID EXT <<< "$FIELDS"

        [[ "$STATE" == "Succeeded" ]] || err "$app exists but is in state '$STATE'"

        if [[ "$ENV_ID" != *"/managedEnvironments/${ENV_NAME}" ]]; then
            err "$app exists in a different environment ($ENV_ID)"
        fi

        if [[ "$ingress" != "external" && "$EXT" == "true" ]]; then
            warn "$app currently has EXTERNAL ingress; the deploy will switch it to $ingress"
        fi
    done
    ok "$NEW app(s) will be created, $EXISTING already exist and will be updated"
else
    warn "Skipped (environment not ready)"
fi

# ------------------------------------------------------------
# 8. Resource totals
# ------------------------------------------------------------

section "Planned capacity"

echo "  vCPU at min replicas : $TOTAL_CPU_MIN"
echo "  vCPU at max replicas : $TOTAL_CPU_MAX"
echo "  Memory at max (Gi)   : $TOTAL_MEM_MAX"
echo "  Check these against your regional Container Apps quota:"
echo "  https://portal.azure.com/#view/Microsoft_Azure_Capacity/QuotaMenuBlade"

# ------------------------------------------------------------
# Summary
# ------------------------------------------------------------

printf '\n============================================================\n'
printf ' PRE-FLIGHT: %d error(s), %d warning(s)\n' "$ERRORS" "$WARNINGS"
printf '============================================================\n'

if (( ERRORS > 0 )); then
    echo "NOT READY. Fix the [FAIL] items above before deploying."
    exit 1
fi

echo "READY. No blocking problems found."
echo "This does not test the apps themselves; run the smoke test after deploying."
exit 0