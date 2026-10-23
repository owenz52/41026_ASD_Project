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

    if [[ -z "$fqdn" || "$fqdn" == "None" ]]; then
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
done

# Preserve native Nginx variables such as $host, $uri,
# $proxy_host and $http_x_forwarded_proto during envsubst.
NGINX_ENVSUBST_FILTER='^(ENROLMENT_FRONTEND_URL|ASSESSMENT_FRONTEND_URL|CALENDAR_FRONTEND_URL|NOTES_FRONTEND_URL|EXAMS_FRONTEND_URL|AUTH_SERVICE_URL|ENROLMENT_SERVICE_URL|ASSESSMENT_SERVICE_URL|CALENDAR_SERVICE_URL|NOTES_SERVICE_URL|EXAMS_SERVICE_URL)$'

ENV_VARS+=("NGINX_ENVSUBST_FILTER=$NGINX_ENVSUBST_FILTER")

echo "Updating environment variables on $PORTAL_APP..."

az containerapp update \
    --name "$PORTAL_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --set-env-vars "${ENV_VARS[@]}" \
    --output none

echo "Portal environment variables configured."

az containerapp show \
    --name "$PORTAL_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --query 'properties.template.containers[0].env[].name' \
    --output table