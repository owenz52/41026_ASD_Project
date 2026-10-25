
#!/usr/bin/env bash
set -Eeuo pipefail

# ============================================================
# Project: Build and Push Docker Images to Azure ACR
#
# Checks whether each image tag already exists in ACR.
# Existing images are skipped unless FORCE_REBUILD=true.
#
# This script does NOT deploy containers.
# ============================================================

RESOURCE_GROUP="${RESOURCE_GROUP:-project-rg}"
REGISTRY_NAME="${REGISTRY_NAME:-}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
FORCE_REBUILD="${FORCE_REBUILD:-false}"

trap 'echo "ERROR: Script failed near line ${LINENO}. Check the output above." >&2' ERR

echo "=================================================="
echo " Project Image Build and Push"
echo "=================================================="

# ------------------------------------------------------------
# 1. Check prerequisites and Azure access
# ------------------------------------------------------------

for command in az docker; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "ERROR: Required command '$command' was not found." >&2
        exit 1
    fi
done

echo
echo "[1/5] Checking Azure login..."

if ! az account show --output none 2>/dev/null; then
    echo "ERROR: Not logged into Azure. Run: az login" >&2
    exit 1
fi

if ! az group show \
    --name "$RESOURCE_GROUP" \
    --output none 2>/dev/null; then
    echo "ERROR: Resource group '$RESOURCE_GROUP' was not found or is inaccessible." >&2
    exit 1
fi

# Read registry name from resource group tags if not provided.
if [[ -z "$REGISTRY_NAME" ]]; then
    REGISTRY_NAME="$(
        az group show \
            --name "$RESOURCE_GROUP" \
            --query "tags.registryName" \
            --output tsv
    )"
fi

if [[ -z "$REGISTRY_NAME" || "$REGISTRY_NAME" == "None" ]]; then
    echo "ERROR: Registry name is missing from resource group tags." >&2
    echo "Set REGISTRY_NAME or add the registryName resource group tag." >&2
    exit 1
fi

echo "Resource group: $RESOURCE_GROUP"
echo "Registry:       $REGISTRY_NAME"
echo "Image tag:      $IMAGE_TAG"
echo "Force rebuild:  $FORCE_REBUILD"

echo
echo "[2/5] Checking Docker..."

docker info >/dev/null
echo "Docker engine is running."

# ------------------------------------------------------------
# 2. Locate project root
# ------------------------------------------------------------

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "$SCRIPT_DIR/docker-compose.yml" ]]; then
    PROJECT_ROOT="$SCRIPT_DIR"
elif [[ -f "$SCRIPT_DIR/../docker-compose.yml" ]]; then
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
    echo "ERROR: Could not locate docker-compose.yml." >&2
    echo "Expected it in the project root or the parent of scripts/." >&2
    exit 1
fi

cd "$PROJECT_ROOT"

echo "Project root: $PROJECT_ROOT"

# ------------------------------------------------------------
# 3. Define all 18 images
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

total=0

while IFS='|' read -r image context dockerfile; do
    [[ -n "$image" ]] || continue
    total=$((total + 1))

    if [[ ! -d "$context" ]]; then
        echo "ERROR: Missing build context for $image: $context" >&2
        exit 1
    fi

    if [[ -n "$dockerfile" ]]; then
        dockerfile_path="$context/$dockerfile"
    else
        dockerfile_path="$context/Dockerfile"
    fi

    if [[ ! -f "$dockerfile_path" ]]; then
        echo "ERROR: Missing Dockerfile for $image: $dockerfile_path" >&2
        exit 1
    fi

    echo "OK: $image"
done <<< "$IMAGES"

if [[ "$total" -ne 18 ]]; then
    echo "ERROR: Expected 18 images, but found $total definitions." >&2
    exit 1
fi

echo "All $total build contexts and Dockerfiles are present."

# ------------------------------------------------------------
# 4. Check registry and authenticate
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

if [[ -z "$LOGIN_SERVER" || "$LOGIN_SERVER" == "None" ]]; then
    echo "ERROR: Could not retrieve the registry login server." >&2
    exit 1
fi

echo "Registry login server: $LOGIN_SERVER"
echo "Logging Docker into Azure Container Registry..."

az acr login --name "$REGISTRY_NAME"

# Retrieve repositories once. Stop if authentication or permissions fail.

echo "Retrieving existing ACR repositories..."

EXISTING_REPOSITORIES="$(
    az acr repository list \
        --name "$REGISTRY_NAME" \
        --output tsv
)"

echo "ACR repository list retrieved successfully."

# ------------------------------------------------------------
# 5. Skip existing tags, build and push missing tags
# ------------------------------------------------------------

echo
echo "[5/5] Checking, building and pushing images..."
echo "This may take some time. Keep this terminal open."

built=0
skipped=0
count=0

while IFS='|' read -r image context dockerfile; do
    [[ -n "$image" ]] || continue

    count=$((count + 1))
    IMAGE_URI="$LOGIN_SERVER/$image:$IMAGE_TAG"
    IMAGE_EXISTS=false

    echo
    echo "=================================================="
    echo "[$count/$total] Checking: $image:$IMAGE_TAG"
    echo "=================================================="

    if [[ "$FORCE_REBUILD" != "true" ]]; then
        REPOSITORY_EXISTS=false

        while IFS= read -r existing_repository; do
            if [[ "$existing_repository" == "$image" ]]; then
                REPOSITORY_EXISTS=true
                break
            fi
        done <<< "$EXISTING_REPOSITORIES"

        if [[ "$REPOSITORY_EXISTS" == "true" ]]; then
            EXISTING_TAGS="$(
                az acr repository show-tags \
                    --name "$REGISTRY_NAME" \
                    --repository "$image" \
                    --output tsv
            )"

            while IFS= read -r existing_tag; do
                if [[ "$existing_tag" == "$IMAGE_TAG" ]]; then
                    IMAGE_EXISTS=true
                    break
                fi
            done <<< "$EXISTING_TAGS"
        fi
    fi

    if [[ "$IMAGE_EXISTS" == "true" ]]; then
        echo "SKIPPING: Image already exists in ACR."
        echo "Existing image: $IMAGE_URI"
        skipped=$((skipped + 1))
        continue
    fi

    echo "Image tag not found. Building: $IMAGE_URI"

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

    echo "Pushing: $IMAGE_URI"
    docker push "$IMAGE_URI"

    echo "SUCCESS: $IMAGE_URI"
    built=$((built + 1))

done <<< "$IMAGES"

# ------------------------------------------------------------
# 6. Verify and summarise
# ------------------------------------------------------------

echo
echo "=================================================="
echo " Image Build and Push Summary"
echo "=================================================="
echo "Images checked: $total"
echo "Images built and pushed: $built"
echo "Images skipped: $skipped"
echo
echo "Repositories currently in Azure Container Registry:"

az acr repository list \
    --name "$REGISTRY_NAME" \
    --output table

echo
echo "Image processing completed."
echo "NOTE: This script does not deploy the services to Azure."
