#!/usr/bin/env bash
set -Eeuo pipefail

# ============================================================
# Project: Build and Push All Docker Images to Azure ACR
# Builds locally with Docker, then pushes to Azure.
# This script does NOT deploy containers.
# ============================================================

RESOURCE_GROUP="${RESOURCE_GROUP:-project-rg}"
REGISTRY_NAME="${REGISTRY_NAME:-$(az group show --name "${RESOURCE_GROUP:-project-rg}" --query "tags.registryName" --output tsv)}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Locate the project root, even when this script is launched
# from a different working directory.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "$SCRIPT_DIR/docker-compose.yml" ]]; then
    PROJECT_ROOT="$SCRIPT_DIR"
elif [[ -f "$SCRIPT_DIR/../docker-compose.yml" ]]; then
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
    echo "ERROR: Could not locate docker-compose.yml."
    echo "Expected it in the project root or the parent of scripts/."
    exit 1
fi

cd "$PROJECT_ROOT"

trap 'echo "ERROR: Script failed near line ${LINENO}. Check the output above." >&2' ERR

echo "=================================================="
echo " Project Image Build and Push"
echo "=================================================="
echo "Project root : $PROJECT_ROOT"
echo "Resource group: $RESOURCE_GROUP"
echo "Registry     : $REGISTRY_NAME"
echo "Image tag    : $IMAGE_TAG"
echo "=================================================="

# ------------------------------------------------------------
# 1. Check prerequisites
# ------------------------------------------------------------

for command in az docker; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "ERROR: Required command '$command' was not found."
        exit 1
    fi
done

echo
echo "[1/5] Checking Azure login..."

if ! az account show --output none; then
    echo "ERROR: Not logged into Azure. Run: az login"
    exit 1
fi

az group show \
    --name "$RESOURCE_GROUP" \
    --output none

echo "Azure login and resource group OK."

echo
echo "[2/5] Checking Docker..."

docker info >/dev/null
echo "Docker engine is running."

# ------------------------------------------------------------
# 2. Define all 18 images
#
# Format: image-name|build-context|Dockerfile-relative-to-context
# An empty Dockerfile field means context/Dockerfile.
# ------------------------------------------------------------

IMAGES=$(cat <<'IMAGE_LIST'
portal-frontend|./shared/frontend|
auth-backend|./shared/backend|
user-database|./shared/database|
assessment-frontend|./student-adrianvoljak/frontend|
assessment-backend|./student-adrianvoljak|backend/Dockerfile
assessment-database|./student-adrianvoljak/database|
calendar-frontend|./student-voreaksanith/frontend|
calendar-backend|./student-voreaksanith|backend/Dockerfile
calendar-database|./student-voreaksanith/database|
enrolment-frontend|./student-yulinzhu/frontend|
enrolment-backend|./student-yulinzhu|backend/Dockerfile
enrolment-database|./student-yulinzhu/database|
notebook-frontend|./student-yunchungchang/frontend|
notebook-backend|./student-yunchungchang|backend/Dockerfile
notebook-database|./student-yunchungchang/database|
exam-frontend|./student-caydenyip/frontend|
exam-backend|./student-caydenyip|backend/Dockerfile
exam-database|./student-caydenyip/database|
IMAGE_LIST
)

# Validate every context and Dockerfile before building anything.
echo
echo "[3/5] Validating all build contexts..."

while IFS='|' read -r image context dockerfile; do
    [[ -n "$image" ]] || continue

    if [[ ! -d "$context" ]]; then
        echo "ERROR: Missing build context for $image: $context"
        exit 1
    fi

    if [[ -n "$dockerfile" ]]; then
        dockerfile_path="$context/$dockerfile"
    else
        dockerfile_path="$context/Dockerfile"
    fi

    if [[ ! -f "$dockerfile_path" ]]; then
        echo "ERROR: Missing Dockerfile for $image: $dockerfile_path"
        exit 1
    fi

    echo "OK: $image"
done <<< "$IMAGES"

echo "All 18 build contexts and Dockerfiles are present."

# ------------------------------------------------------------
# 3. Check registry and authenticate
# ------------------------------------------------------------

echo
echo "[4/5] Checking Azure Container Registry..."

LOGIN_SERVER="$(
    az acr show \
        --name "$REGISTRY_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query loginServer \
        --output tsv
)"

if [[ -z "$LOGIN_SERVER" || "$LOGIN_SERVER" == "null" ]]; then
    echo "ERROR: Could not retrieve the registry login server."
    exit 1
fi

echo "Registry login server: $LOGIN_SERVER"
echo "Logging Docker into Azure Container Registry..."

az acr login --name "$REGISTRY_NAME"

# ------------------------------------------------------------
# 4. Build locally and push each image
# ------------------------------------------------------------

echo
echo "[5/5] Building and pushing images..."
echo "This may take some time. Keep this terminal open."

total=18
count=0

while IFS='|' read -r image context dockerfile; do
    [[ -n "$image" ]] || continue

    count=$((count + 1))
    IMAGE_URI="$LOGIN_SERVER/$image:$IMAGE_TAG"

    echo
    echo "=================================================="
    echo "[$count/$total] Building: $image"
    echo "Context: $context"
    echo "Target:  $IMAGE_URI"
    echo "=================================================="

    if [[ -n "$dockerfile" ]]; then
        docker build \
            --tag "$IMAGE_URI" \
            --file "$context/$dockerfile" \
            "$context"
    else
        docker build \
            --tag "$IMAGE_URI" \
            "$context"
    fi

    echo "[$count/$total] Pushing: $image"
    docker push "$IMAGE_URI"

    echo "SUCCESS: $IMAGE_URI"
done <<< "$IMAGES"

# ------------------------------------------------------------
# 5. Verify repositories in ACR
# ------------------------------------------------------------

echo
echo "=================================================="
echo "All images built and pushed successfully!"
echo "=================================================="
echo
echo "Repositories currently in Azure Container Registry:"

az acr repository list \
    --name "$REGISTRY_NAME" \
    --output table

echo
echo "Image build and push completed."
echo "NOTE: This script does not deploy the services to Azure."