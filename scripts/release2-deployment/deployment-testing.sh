#!/usr/bin/env bash
set -Eeuo pipefail

# ============================================================
# Project: Release 2 Deployment Testing
#
# Purpose:
#   - Reads the deployed portal Container App name from tags.
#   - Retrieves its public HTTPS endpoint.
#   - Validates the health endpoint.
#   - Writes deployment-results.md.
#
# Resource group : asd-release2-rg
# Region         : australiaeast
# Report         : reports/deployment-results.md
#
# Prerequisites:
#   1. scripts/release2-deployment/env-setup.sh
#   2. scripts/release2-deployment/deploy-azure-env.sh
#   3. Azure CLI installed and authenticated
# ============================================================

RESOURCE_GROUP="${RESOURCE_GROUP:-asd-release2-rg}"
REPORT_FILE="reports/release2-deployment/deployment-results.md"
HEALTH_PATH="${HEALTH_PATH:-/}"

echo "=== Release 2 Deployment Testing ==="

# Step 1: Confirm the resource group exists.
if ! az group show \
    --name "$RESOURCE_GROUP" \
    --output none 2>/dev/null; then
    echo "ERROR: Resource group '$RESOURCE_GROUP' was not found or is inaccessible." >&2
    echo "Run the Release 2 environment setup first." >&2
    exit 1
fi

# Step 2: Read the shared portal app name from resource group tags.
APP_NAME=$(az group show \
    --name "$RESOURCE_GROUP" \
    --query "tags.frontendAppName" \
    --output tsv)

if [[ -z "$APP_NAME" || "$APP_NAME" == "None" ]]; then
    echo "ERROR: Resource group '$RESOURCE_GROUP' is missing the frontendAppName tag." >&2
    echo "Check the tags created by scripts/release2-deployment/env-setup.sh." >&2
    exit 1
fi

echo "Portal Container App: $APP_NAME"

# Step 3: Retrieve the Container App's public hostname.
APP_URL=$(az containerapp show \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "properties.configuration.ingress.fqdn" \
    --output tsv)

if [[ -z "$APP_URL" || "$APP_URL" == "None" ]]; then
    echo "ERROR: Could not retrieve the portal's public ingress hostname." >&2
    echo "Check that the Container App exists and public ingress is configured." >&2
    exit 1
fi

FRONTEND_URL="https://${APP_URL}"
HEALTH_URL="${FRONTEND_URL}${HEALTH_PATH}"

echo "Frontend URL: $FRONTEND_URL"
echo "Health URL:   $HEALTH_URL"

# Step 4: Validate the health endpoint.
# --connect-timeout limits connection setup time.
# --max-time limits the total request duration.
# --location follows HTTP redirects.
HTTP_STATUS=$(curl \
    --silent \
    --show-error \
    --output /dev/null \
    --write-out "%{http_code}" \
    --location \
    --connect-timeout 10 \
    --max-time 30 \
    "$HEALTH_URL" 2>/dev/null) || HTTP_STATUS="000"

if [[ "$HTTP_STATUS" == "200" ]]; then
    STATUS="Success"
    VALIDATION="HTTP ${HTTP_STATUS} OK"
else
    STATUS="Failed"
    VALIDATION="HTTP ${HTTP_STATUS}"
fi

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Step 5: Generate the deployment report.
mkdir -p "$(dirname "$REPORT_FILE")"

cat > "$REPORT_FILE" <<EOF
# Release 2 Deployment Report

## Azure Container Apps

Resource Group: $RESOURCE_GROUP

Deployment Status: $STATUS

Portal Container App: $APP_NAME

Frontend URL: $FRONTEND_URL

Health Endpoint: $HEALTH_URL

Validation Result: $VALIDATION

Timestamp (UTC): $TIMESTAMP

Reviewer Notes: Pending /review-deployment review.

## Validation Details

- Checks the public portal endpoint over HTTPS.
- Follows HTTP redirects.
- Uses HTTP 200 as the success criterion.
- HTTP 000 indicates that curl could not obtain an HTTP response.
- This test validates endpoint availability only; it does not verify all 18 services or their individual functionality.
EOF

echo
echo "=== Deployment Testing Complete ==="
echo "Status: $STATUS"
echo "Report: $REPORT_FILE"

cat "$REPORT_FILE"

# Return a failure exit code if the endpoint did not pass validation.
if [[ "$STATUS" != "Success" ]]; then
    exit 1
fi
