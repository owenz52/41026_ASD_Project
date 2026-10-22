#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

RESOURCE_GROUP="${RESOURCE_GROUP:-asd-release2-rg}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse HEAD)}"

for tool in az python3; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "ERROR: Required tool not found: $tool" >&2
        exit 1
    fi
done

if [[ ! "$IMAGE_TAG" =~ ^[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,127}$ ]]; then
    echo "ERROR: Invalid IMAGE_TAG: $IMAGE_TAG" >&2
    exit 1
fi

SERVICE_LIST="$(mktemp)"
trap 'rm -f "$SERVICE_LIST"' EXIT

python3 - "$PROJECT_ROOT" > "$SERVICE_LIST" <<'PY'
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
services = json.loads(
    (root / "deploy/azure/services.json").read_text(encoding="utf-8")
)["services"]
if len(services) != 18:
    raise ValueError("Expected exactly 18 services")

names = set()
for service in services:
    name = service["name"]
    if not re.fullmatch(r"[a-z][a-z0-9-]*", name):
        raise ValueError(f"Invalid service name: {name}")
    if name in names:
        raise ValueError(f"Duplicate service: {name}")
    names.add(name)
    context = (root / service["context"]).resolve()
    dockerfile = (context / service["dockerfile"]).resolve()
    if not context.is_relative_to(root):
        raise ValueError(f"Build context is outside repository: {name}")
    if not dockerfile.is_relative_to(context):
        raise ValueError(f"Dockerfile is outside build context: {name}")
    if not context.is_dir() or not dockerfile.is_file():
        raise ValueError(f"Missing build context or Dockerfile: {name}")
    if name == "portal-frontend" and context != root:
        raise ValueError("Portal build context must be repository root")
    relative_dockerfile = str(dockerfile.relative_to(context))
    values = [name, str(context), relative_dockerfile]
    if any("\t" in value or "\n" in value for value in values):
        raise ValueError(f"Unsupported whitespace in service paths: {name}")
    print("\t".join(values))

if "portal-frontend" not in names:
    raise ValueError("Missing portal-frontend")
PY

echo "=== Release 2 Image Build ==="
echo "Resource group: $RESOURCE_GROUP"
echo "Image tag: $IMAGE_TAG"

az account show \
    --query '{subscription:name,id:id}' \
    --output table

REGISTRY_NAME="$(az group show \
    --name "$RESOURCE_GROUP" \
    --query tags.registryName \
    --output tsv)"

LOCATION="$(az group show \
    --name "$RESOURCE_GROUP" \
    --query tags.location \
    --output tsv)"

if [[ -z "$REGISTRY_NAME" || "$REGISTRY_NAME" == "None" \
   || -z "$LOCATION" || "$LOCATION" == "None" ]]; then
    echo "ERROR: Missing registryName or location resource group tags." >&2
    echo "Run scripts/release2-deployment/env-setup.sh first." >&2
    exit 1
fi

EXISTING_REGISTRY="$(az acr list \
    --resource-group "$RESOURCE_GROUP" \
    --query "[?name=='${REGISTRY_NAME}'].name | [0]" \
    --output tsv)"

if [[ -z "$EXISTING_REGISTRY" || "$EXISTING_REGISTRY" == "None" ]]; then
    echo "Creating ACR: $REGISTRY_NAME"
    az acr create \
        --resource-group "$RESOURCE_GROUP" \
        --name "$REGISTRY_NAME" \
        --location "$LOCATION" \
        --sku Basic \
        --admin-enabled false \
        --output none
else
    echo "Reusing ACR: $REGISTRY_NAME"
fi

LOGIN_SERVER="$(az acr show \
    --resource-group "$RESOURCE_GROUP" \
    --name "$REGISTRY_NAME" \
    --query loginServer \
    --output tsv)"

python3 - "$LOGIN_SERVER" <<'PY'
import socket
import sys
import time

hostname = sys.argv[1]
for attempt in range(24):
    try:
        socket.getaddrinfo(hostname, 443)
        print(f"Registry DNS ready: {hostname}")
        break
    except socket.gaierror:
        if attempt == 23:
            raise SystemExit(f"DNS lookup timed out: {hostname}")
        time.sleep(5)
PY

COUNT=0

while IFS=$'\t' read -r NAME CONTEXT DOCKERFILE; do
    echo ""
    echo "Building and pushing: ${LOGIN_SERVER}/${NAME}:${IMAGE_TAG}"
    (
        cd "$CONTEXT"
        az acr build \
            --resource-group "$RESOURCE_GROUP" \
            --registry "$REGISTRY_NAME" \
            --platform linux/amd64 \
            --image "${NAME}:${IMAGE_TAG}" \
            --file "$DOCKERFILE" \
            .
    )

    COUNT=$((COUNT + 1))
done < "$SERVICE_LIST"

if [[ "$COUNT" -ne 18 ]]; then
    echo "ERROR: Expected 18 completed builds; got $COUNT." >&2
    exit 1
fi

echo ""
echo "=== Image Build Complete ==="
echo "Successfully built and pushed $COUNT images."
echo "Registry: $LOGIN_SERVER"
echo "IMAGE_TAG=$IMAGE_TAG"
echo "Use this same IMAGE_TAG for application deployment."