#!/usr/bin/env bash
set -Eeuo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-project-rg}"
URL_SCHEME="${URL_SCHEME:-https}"

command -v az >/dev/null 2>&1 || {
    echo "ERROR: Azure CLI not found."
    exit 1
}

az account show --output none || {
    echo "ERROR: Run az login first."
    exit 1
}

# Get the ingress URL of a Container App.
app_url() {
    local app="$1"
    local fqdn

    fqdn="$(az containerapp show \
        --name "$app" \
        --resource-group "$RESOURCE_GROUP" \
        --query 'properties.configuration.ingress.fqdn' \
        --output tsv)"

    if [[ -z "$fqdn" || "$fqdn" == "None" ]]; then
        echo "ERROR: No ingress FQDN for $app." >&2
        return 1
    fi

    printf '%s://%s' "$URL_SCHEME" "$fqdn"
}

# Backend -> database mapping.
declare -a MAPPINGS=(
    "project-auth|project-user-db"
    "project-enrolment-api|project-enrolment-db"
    "project-assessment-api|project-assessment-db"
    "project-calendar-api|project-calendar-db"
    "project-notebook-api|project-notebook-db"
    "project-exam-api|project-exam-db"
)

# Validate all backend and database apps first.
for mapping in "${MAPPINGS[@]}"; do
    IFS='|' read -r backend database <<< "$mapping"

    for app in "$backend" "$database"; do
        echo "Checking $app..."

        az containerapp show \
            --name "$app" \
            --resource-group "$RESOURCE_GROUP" \
            --output none
    done
done

echo
echo "Configuring database URLs..."

for mapping in "${MAPPINGS[@]}"; do
    IFS='|' read -r backend database <<< "$mapping"

    DATABASE_SERVICE_URL="$(app_url "$database")"

    echo "Setting DATABASE_SERVICE_URL on $backend..."

    az containerapp update \
        --name "$backend" \
        --resource-group "$RESOURCE_GROUP" \
        --set-env-vars \
            "DATABASE_SERVICE_URL=$DATABASE_SERVICE_URL" \
        --output none
done

# The exam API calls the enrolment API.
ENROLMENT_DB_URL="$(app_url project-enrolment-db)"

echo "Setting ENROLMENT_SERVICE_URL on project-exam-api..."

az containerapp update \
    --name project-exam-api \
    --resource-group "$RESOURCE_GROUP" \
    --set-env-vars \
        "ENROLMENT_SERVICE_URL=$ENROLMENT_DB_URL" \
    --output none

echo
echo "Backend environment variables configured."


# Calendar API -> assessment and exam database services

ASSESSMENT_DB_URL="$(app_url project-assessment-db http)"
EXAM_DB_URL="$(app_url project-exam-db http)"

echo "Setting ASSESSMENT_SERVICE_URL on project-calendar-api..."

az containerapp update \
  --name project-calendar-api \
  --resource-group "$RESOURCE_GROUP" \
  --set-env-vars "ASSESSMENT_SERVICE_URL=$ASSESSMENT_DB_URL" \
  --output none

echo "Setting EXAM_SERVICE_URL on project-calendar-api..."

az containerapp update \
  --name project-calendar-api \
  --resource-group "$RESOURCE_GROUP" \
  --set-env-vars "EXAM_SERVICE_URL=$EXAM_DB_URL" \
  --output none

echo "Calendar API service URLs configured."


# ============================================================
# Disable AI, MCP and RAG for all backend services
# ============================================================

echo
echo "Disabling AI, MCP and RAG on all backends..."

for backend in \
    project-auth \
    project-enrolment-api \
    project-assessment-api \
    project-calendar-api \
    project-notebook-api \
    project-exam-api
do
    echo "Updating $backend..."

    az containerapp update \
        --name "$backend" \
        --resource-group "$RESOURCE_GROUP" \
        --set-env-vars \
            AI_ENABLED=false \
            MCP_ENABLED=false \
            RAG_ENABLED=false \
        --output none

    echo "$backend: AI, MCP and RAG disabled."
done

echo
echo "All backend environment variables configured."