#!/usr/bin/env bash
set -Eeuo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-project-rg}"
PORTAL_APP="${PORTAL_APP:-project-portal}"

# Verify Azure CLI and login.
command -v az >/dev/null 2>&1 || {
    echo "ERROR: Azure CLI not found."
    exit 1
}

az account show --output none || {
    echo "ERROR: Run az login first."
    exit 1
}

# Resolve an app's HTTPS ingress URL.
app_url() {
    local app="$1"
    local fqdn

    fqdn="$(az containerapp show \
        --name "$app" \
        --resource-group "$RESOURCE_GROUP" \
        --query 'properties.configuration.ingress.fqdn' \
        --output tsv)"

    if [[ -z "$fqdn" || "$fqdn" == "None" || "$fqdn" == "null" ]]; then
        echo "ERROR: No ingress FQDN for $app." >&2
        return 1
    fi

    printf 'https://%s' "$fqdn"
}

# Frontend URL mappings.
declare -a FRONTENDS=(
    "ENROLMENT_FRONTEND_URL|project-enrolment-frontend"
    "ASSESSMENT_FRONTEND_URL|project-assessment-frontend"
    "CALENDAR_FRONTEND_URL|project-calendar-frontend"
    "NOTES_FRONTEND_URL|project-notebook-frontend"
    "EXAMS_FRONTEND_URL|project-exam-frontend"
)

# API URL mappings.
declare -a APIS=(
    "AUTH_SERVICE_URL|project-auth"
    "ENROLMENT_SERVICE_URL|project-enrolment-api"
    "ASSESSMENT_SERVICE_URL|project-assessment-api"
    "CALENDAR_SERVICE_URL|project-calendar-api"
    "NOTES_SERVICE_URL|project-notebook-api"
    "EXAMS_SERVICE_URL|project-exam-api"
)

# Check the portal exists.
az containerapp show \
    --name "$PORTAL_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --output none

declare -a ENV_VARS=()
declare -A EXPECTED=()

# Resolve frontend URLs.
for mapping in "${FRONTENDS[@]}"; do
    IFS='|' read -r variable app <<< "$mapping"

    echo "Checking $app..."

    az containerapp show \
        --name "$app" \
        --resource-group "$RESOURCE_GROUP" \
        --output none

    url="$(app_url "$app")"
    ENV_VARS+=("$variable=$url")
    EXPECTED["$variable"]="$url"
done

# Resolve API URLs.
for mapping in "${APIS[@]}"; do
    IFS='|' read -r variable app <<< "$mapping"

    echo "Checking $app..."

    az containerapp show \
        --name "$app" \
        --resource-group "$RESOURCE_GROUP" \
        --output none

    url="$(app_url "$app")"
    ENV_VARS+=("$variable=$url")
    EXPECTED["$variable"]="$url"
done

# Preserve native Nginx variables such as $host, $uri,
# $proxy_host and $http_x_forwarded_proto during envsubst.
NGINX_ENVSUBST_FILTER='^(ENROLMENT_FRONTEND_URL|ASSESSMENT_FRONTEND_URL|CALENDAR_FRONTEND_URL|NOTES_FRONTEND_URL|EXAMS_FRONTEND_URL|AUTH_SERVICE_URL|ENROLMENT_SERVICE_URL|ASSESSMENT_SERVICE_URL|CALENDAR_SERVICE_URL|NOTES_SERVICE_URL|EXAMS_SERVICE_URL)$'

ENV_VARS+=("NGINX_ENVSUBST_FILTER=$NGINX_ENVSUBST_FILTER")
EXPECTED["NGINX_ENVSUBST_FILTER"]="$NGINX_ENVSUBST_FILTER"

# Read current environment variables from the portal.
echo "Reading current environment variables from $PORTAL_APP..."

CURRENT_ENV_JSON="$(az containerapp show \
    --name "$PORTAL_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --query 'properties.template.containers[0].env' \
    --output json)"

# Compare the expected variables with the current configuration.
NEEDS_UPDATE=false

for variable in "${!EXPECTED[@]}"; do
    expected_value="${EXPECTED[$variable]}"

    current_value="$(printf '%s' "$CURRENT_ENV_JSON" |
        VARIABLE="$variable" python -c '
import json
import os
import sys

variable = os.environ["VARIABLE"]
env_vars = json.load(sys.stdin) or []

for item in env_vars:
    if item.get("name") == variable:
        print(item.get("value", ""))
        break
')"

    if [[ "$current_value" != "$expected_value" ]]; then
        echo "CHANGE: $variable is missing or differs."
        NEEDS_UPDATE=true
    else
        echo "UNCHANGED: $variable"
    fi
done

# Update only if at least one expected value differs.
if [[ "$NEEDS_UPDATE" == false ]]; then
    echo "All expected portal environment variables already match."
    echo "Skipping update; no deployment configuration change is needed."
else
    echo "Updating environment variables on $PORTAL_APP..."

    az containerapp update \
        --name "$PORTAL_APP" \
        --resource-group "$RESOURCE_GROUP" \
        --set-env-vars "${ENV_VARS[@]}" \
        --output none

    echo "Portal environment variables updated."
fi

# Display the configured variable names.
az containerapp show \
    --name "$PORTAL_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --query 'properties.template.containers[0].env[].name' \
    --output table
