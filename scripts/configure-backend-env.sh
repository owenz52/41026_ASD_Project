#!/usr/bin/env bash
set -Eeuo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-project-rg}"
URL_SCHEME="${URL_SCHEME:-https}"

command -v az >/dev/null 2>&1 || {
    echo "ERROR: Azure CLI not found." >&2
    exit 1
}

az account show --output none || {
    echo "ERROR: Run az login first." >&2
    exit 1
}

# Get the ingress URL of a Container App.
# Optional second argument overrides URL_SCHEME.
app_url() {
    local app="$1"
    local scheme="${2:-$URL_SCHEME}"
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

    printf '%s://%s' "$scheme" "$fqdn"
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

# Expected environment variables per app.
# Associative arrays store each app's desired variable values.
declare -A EXPECTED=()

set_expected() {
    local app="$1"
    local variable="$2"
    local value="$3"

    EXPECTED["$app|$variable"]="$value"
}

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
echo "Resolving database service URLs..."

# Main backend -> database variables.
for mapping in "${MAPPINGS[@]}"; do
    IFS='|' read -r backend database <<< "$mapping"

    database_url="$(app_url "$database")"
    set_expected "$backend" "DATABASE_SERVICE_URL" "$database_url"
done

# The exam API calls the enrolment service.
# This preserves the original script's database URL mapping.
# Change to project-enrolment-api if the exam API needs that API.
enrolment_db_url="$(app_url project-enrolment-db)"
set_expected "project-exam-api" "ENROLMENT_SERVICE_URL" "$enrolment_db_url"

# Calendar API -> assessment and exam database services.
assessment_db_url="$(app_url project-assessment-db http)"
exam_db_url="$(app_url project-exam-db http)"

set_expected "project-calendar-api" "ASSESSMENT_SERVICE_URL" "$assessment_db_url"
set_expected "project-calendar-api" "EXAM_SERVICE_URL" "$exam_db_url"

# Disable AI, MCP, RAG and multi-agent on each backend.
for backend in \
    project-auth \
    project-enrolment-api \
    project-assessment-api \
    project-calendar-api \
    project-notebook-api \
    project-exam-api
do
    set_expected "$backend" "AI_ENABLED" "false"
    set_expected "$backend" "MCP_ENABLED" "false"
    set_expected "$backend" "RAG_ENABLED" "false"
    set_expected "$backend" "MULTI_AGENT_ENABLED" "false"
done

# Apply only differences. Each app gets at most one update.
declare -A APP_CHANGES=()

for key in "${!EXPECTED[@]}"; do
    app="${key%%|*}"
    variable="${key#*|}"
    expected_value="${EXPECTED[$key]}"

    current_value="$(az containerapp show \
        --name "$app" \
        --resource-group "$RESOURCE_GROUP" \
        --query "properties.template.containers[0].env[?name=='${variable}'].value | [0]" \
        --output tsv)"

    if [[ "$current_value" != "$expected_value" ]]; then
        echo "CHANGE: $app -> $variable"
        APP_CHANGES["$app"]+="$variable=$expected_value"$'\n'
    else
        echo "UNCHANGED: $app -> $variable"
    fi
done

echo
echo "Applying required environment-variable changes..."

for app in "${!APP_CHANGES[@]}"; do
    mapfile -t changes < <(
        printf '%s' "${APP_CHANGES[$app]}" | sed '/^$/d'
    )

    if ((${#changes[@]} == 0)); then
        continue
    fi

    echo "Updating $app with ${#changes[@]} changed variable(s)..."

    az containerapp update \
        --name "$app" \
        --resource-group "$RESOURCE_GROUP" \
        --set-env-vars "${changes[@]}" \
        --output none

    echo "Updated: $app"
done

if ((${#APP_CHANGES[@]} == 0)); then
    echo "No environment-variable changes were required."
fi

echo
echo "Verifying backend environment variables..."

for backend in \
    project-auth \
    project-enrolment-api \
    project-assessment-api \
    project-calendar-api \
    project-notebook-api \
    project-exam-api
do
    echo
    echo "$backend:"
    az containerapp show \
        --name "$backend" \
        --resource-group "$RESOURCE_GROUP" \
        --query 'properties.template.containers[0].env[].[name,value]' \
        --output table
done

echo
echo "Backend environment-variable configuration complete."
