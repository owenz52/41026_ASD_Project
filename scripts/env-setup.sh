#!/usr/bin/env bash
set -euo pipefail

# Azure environment setup
RESOURCE_GROUP="${RESOURCE_GROUP:-project-rg}"
LOCATION="${LOCATION:-australiaeast}"
REGISTER_PROVIDERS="${REGISTER_PROVIDERS:-true}"

echo "=== Project Environment Setup ==="

# Check prerequisites
if ! command -v az >/dev/null 2>&1; then
    echo "ERROR: Azure CLI is not installed or not available in this terminal."
    exit 1
fi

if ! command -v python >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: Python is required to read existing resource group tags."
    exit 1
fi

if ! az account show >/dev/null 2>&1; then
    echo "ERROR: Please log in to Azure first using: az login"
    exit 1
fi

echo
echo "Selected Azure subscription:"
az account show --query '{Subscription:name, SubscriptionId:id, TenantId:tenantId}' --output table

# Register providers if requested
if [[ "${REGISTER_PROVIDERS,,}" == "true" ]]; then
    echo
    echo "Registering required resource providers..."
    az provider register --namespace Microsoft.App --wait
    az provider register --namespace Microsoft.OperationalInsights --wait
else
    echo
    echo "Skipping resource provider registration."
fi

# Create resource group if it does not exist
echo
if az group show --name "$RESOURCE_GROUP" >/dev/null 2>&1; then
    echo "Using existing resource group: $RESOURCE_GROUP"
else
    echo "Creating resource group: $RESOURCE_GROUP"
    az group create \
        --name "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --output none
fi

# Read existing tags
EXISTING_TAGS="$(az group show --name "$RESOURCE_GROUP" --query 'tags || `{}`' --output json)"

# Use Python to safely read existing tag values
get_tag() {
    local tag_key="$1"
    if command -v python3 >/dev/null 2>&1; then
        python3 -c 'import json,sys; print((json.load(sys.stdin) or {}).get(sys.argv[1], ""))' "$tag_key" <<< "$EXISTING_TAGS"
    else
        python -c 'import json,sys; print((json.load(sys.stdin) or {}).get(sys.argv[1], ""))' "$tag_key" <<< "$EXISTING_TAGS"
    fi
}

# Preserve existing names where possible
SUFFIX="$(printf '%05d' "$(( (RANDOM * 32768 + RANDOM) % 100000 ))")"

REGISTRY_NAME="$(get_tag registryName)"
ENV_NAME="$(get_tag envName)"

if [[ -z "$REGISTRY_NAME" ]]; then
    REGISTRY_NAME="projectregistry${SUFFIX}"
fi

if [[ -z "$ENV_NAME" ]]; then
    ENV_NAME="project-env-${SUFFIX}"
fi

# Service names saved as resource group tags
declare -A SERVICE_NAMES=(
    [portalAppName]="project-portal"
    [authAppName]="project-auth"
    [userDatabaseAppName]="project-user-db"
    [assessmentFrontendAppName]="project-assessment-frontend"
    [assessmentBackendAppName]="project-assessment-api"
    [assessmentDatabaseAppName]="project-assessment-db"
    [calendarFrontendAppName]="project-calendar-frontend"
    [calendarBackendAppName]="project-calendar-api"
    [calendarDatabaseAppName]="project-calendar-db"
    [enrolmentFrontendAppName]="project-enrolment-frontend"
    [enrolmentBackendAppName]="project-enrolment-api"
    [enrolmentDatabaseAppName]="project-enrolment-db"
    [notebookFrontendAppName]="project-notebook-frontend"
    [notebookBackendAppName]="project-notebook-api"
    [notebookDatabaseAppName]="project-notebook-db"
    [examFrontendAppName]="project-exam-frontend"
    [examBackendAppName]="project-exam-api"
    [examDatabaseAppName]="project-exam-db"
)

# Keep any unrelated tags already on the resource group
declare -A ALL_TAGS=()

while IFS=$'\t' read -r key value; do
    if [[ -n "$key" ]]; then
        ALL_TAGS["$key"]="$value"
    fi
done < <(
    if command -v python3 >/dev/null 2>&1; then
        python3 -c 'import json,sys; [print(f"{k}\t{v}") for k,v in (json.load(sys.stdin) or {}).items()]' <<< "$EXISTING_TAGS"
    else
        python -c 'import json,sys; [print("{}\t{}".format(k,v)) for k,v in (json.load(sys.stdin) or {}).items()]' <<< "$EXISTING_TAGS"
    fi
)

# Preserve previously configured service names
for tag_key in "${!SERVICE_NAMES[@]}"; do
    EXISTING_VALUE="$(get_tag "$tag_key")"
    if [[ -n "$EXISTING_VALUE" ]]; then
        SERVICE_NAMES["$tag_key"]="$EXISTING_VALUE"
    fi
done

# Build the complete set of tags
ALL_TAGS[registryName]="$REGISTRY_NAME"
ALL_TAGS[envName]="$ENV_NAME"
ALL_TAGS[location]="$LOCATION"

for tag_key in "${!SERVICE_NAMES[@]}"; do
    ALL_TAGS["$tag_key"]="${SERVICE_NAMES[$tag_key]}"
done

TAG_ARGS=()
for tag_key in "${!ALL_TAGS[@]}"; do
    TAG_ARGS+=("${tag_key}=${ALL_TAGS[$tag_key]}")
done

# Save tags
echo
echo "Saving deployment names to resource group..."
az group update \
    --name "$RESOURCE_GROUP" \
    --tags "${TAG_ARGS[@]}" \
    --output none

echo
echo "=== Environment Setup Complete ==="
echo "Resource group: $RESOURCE_GROUP"
echo "Location: $LOCATION"
echo
az group show --name "$RESOURCE_GROUP" --query tags --output table

echo
echo "Setup complete."
echo "This script only prepares the resource group and records names."
echo "It does NOT create the container registry, environment, apps, or databases."
