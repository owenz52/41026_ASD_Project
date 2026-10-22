#!/bin/bash
set -euo pipefail

# Validates the deployed portal frontend and writes a deployment report.

RESOURCE_GROUP="${RESOURCE_GROUP:-project-rg}"
APP_NAME="${APP_NAME:-project-portal}"
REPORT_FILE="${REPORT_FILE:-reports/deployment-results.md}"
TIMEOUT="${TIMEOUT:-15}"

echo "=== Project Deployment Testing ==="

# Step 1: Check Azure CLI and authentication
if ! command -v az >/dev/null 2>&1; then
  echo "ERROR: Azure CLI (az) is not installed or is not on PATH." >&2
  exit 1
fi

if ! az account show >/dev/null 2>&1; then
  echo "ERROR: You are not logged in to Azure. Run: az login" >&2
  exit 1
fi

# Step 2: Verify the resource group exists
if ! az group show --name "$RESOURCE_GROUP" >/dev/null 2>&1; then
  echo "ERROR: Resource group '$RESOURCE_GROUP' was not found or is inaccessible." >&2
  exit 1
fi

# Step 3: Read the deployed portal's FQDN
echo "Checking Container App: $APP_NAME"

if ! APP_URL=$(az containerapp show \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.configuration.ingress.fqdn" \
  --output tsv); then
  echo "ERROR: Could not find Container App '$APP_NAME' in '$RESOURCE_GROUP'." >&2
  exit 1
fi

if [[ -z "$APP_URL" || "$APP_URL" == "None" ]]; then
  echo "ERROR: The portal has no ingress FQDN. Check its ingress configuration." >&2
  exit 1
fi

# Step 4: Validate the public HTTPS endpoint
if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl is required to test the deployed portal." >&2
  exit 1
fi

APP_HTTPS_URL="https://${APP_URL}"
echo "Validating ${APP_HTTPS_URL} ..."

HTTP_STATUS=$(curl \
  --silent \
  --show-error \
  --output /dev/null \
  --write-out "%{http_code}" \
  --connect-timeout "$TIMEOUT" \
  --max-time 60 \
  "$APP_HTTPS_URL" 2>/dev/null || true)

if [[ "$HTTP_STATUS" == "200" ]]; then
  STATUS="Success"
  VALIDATION="HTTP ${HTTP_STATUS} OK"
else
  STATUS="Failed"
  VALIDATION="HTTP ${HTTP_STATUS:-000} - portal did not return HTTP 200"
fi

# Step 5: Write the deployment report
mkdir -p "$(dirname "$REPORT_FILE")"

cat > "$REPORT_FILE" <<EOF
# Project Deployment Report

## Azure Container Apps

- Resource Group: ${RESOURCE_GROUP}
- Portal App Name: ${APP_NAME}
- Deployment Status: ${STATUS}
- Portal URL: ${APP_HTTPS_URL}
- Validation Result: ${VALIDATION}
- Timestamp (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)

## Validation Scope

This test checks whether the deployed portal's HTTPS endpoint returns HTTP 200.
It does not independently verify login, API routing, database connectivity,
or the availability of AI services.

## Reviewer Notes

Pending review.
EOF

echo
echo "=== Deployment Testing Complete ==="
echo "Status:     $STATUS"
echo "Portal URL: $APP_HTTPS_URL"
echo "Report:     $REPORT_FILE"
echo
cat "$REPORT_FILE"

# Return a failure exit code if the endpoint check failed.
if [[ "$STATUS" != "Success" ]]; then
  exit 1
fi