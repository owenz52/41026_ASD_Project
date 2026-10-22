#!/usr/bin/env bash
set -euo pipefail

RESOURCE_GROUP="project-rg"
APP_NAME="project-portal"

echo "Checking portal deployment..."

URL="$(az containerapp show \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.configuration.ingress.fqdn" \
  --output tsv)"

if [[ -z "$URL" || "$URL" == "null" ]]; then
  echo "FAIL: Portal has no ingress URL."
  exit 1
fi

echo "Testing https://$URL"

curl --fail --silent --show-error \
  --max-time 20 \
  "https://$URL/" \
  --output /dev/null

echo "PASS: Portal returned a successful HTTP response."