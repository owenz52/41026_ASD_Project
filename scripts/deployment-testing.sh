#!/usr/bin/env bash
set -Eeuo pipefail

# Lightweight deployment test:
#   1. finds the deployed frontend Container App
#   2. checks its public URL returns HTTP 200
#   3. writes deployment-results.md
#
# For the full 18-app check, use scripts/deployment-testing-full.sh.
#
# Optional environment variables:
#   RESOURCE_GROUP   default: project-rg
#   FRONTEND_APP     default: the resource group's frontendAppName tag,
#                    else project-portal
#   REPORT_FILE      default: reports/deployment-results.md

# Git Bash / MSYS2 rewrites arguments that start with "/" into Windows paths.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'

RESOURCE_GROUP="${RESOURCE_GROUP:-project-rg}"
REPORT_FILE="${REPORT_FILE:-reports/deployment-results.md}"
APP_NAME="${FRONTEND_APP:-}"

# Some Azure CLI installs print Windows line endings (\r) that corrupt values.
az() { command az "$@" | tr -d '\r'; }

echo "=== Deployment Testing ==="

# Step 1: Find the deployed frontend Container App name
if [[ -z "$APP_NAME" ]]; then
  APP_NAME=$(az group show --name "$RESOURCE_GROUP" --query "tags.frontendAppName" -o tsv)
  if [[ -z "$APP_NAME" || "$APP_NAME" == "None" ]]; then
    APP_NAME="project-portal"
  fi
fi

# Step 2: Get the Container App FQDN
APP_URL=$(az containerapp show \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query properties.configuration.ingress.fqdn -o tsv)

if [[ -z "$APP_URL" || "$APP_URL" == "None" ]]; then
  echo "No public URL found for $APP_NAME in $RESOURCE_GROUP." >&2
  exit 1
fi

# Step 3: Validate the frontend (retries cover a cold start from zero replicas)
echo "Validating https://$APP_URL ..."
HTTP_STATUS="000"
for attempt in 1 2 3 4 5; do
  HTTP_STATUS=$(curl -s -L -o /dev/null -w "%{http_code}" --max-time 60 "https://$APP_URL" || true)
  [[ "$HTTP_STATUS" == "200" ]] && break
  sleep 10
done

if [[ "$HTTP_STATUS" == "200" ]]; then
  STATUS="Success"
  VALIDATION="HTTP $HTTP_STATUS OK"
else
  STATUS="Failed"
  VALIDATION="HTTP $HTTP_STATUS"
fi

# Step 4: Write deployment-results.md
mkdir -p "$(dirname "$REPORT_FILE")"
cat > "$REPORT_FILE" <<EOF
# Deployment Report

## Azure Container Apps

Deployment Status: $STATUS

Frontend App Name: $APP_NAME

Frontend URL: https://$APP_URL

Validation Result: $VALIDATION

Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)

Reviewer Notes: (pending Section 7 AI review)
EOF

echo "=== Deployment Testing Complete ==="
cat "$REPORT_FILE"

[[ "$STATUS" == "Success" ]]