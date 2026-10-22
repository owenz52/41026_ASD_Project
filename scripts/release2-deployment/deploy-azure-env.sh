
#!/usr/bin/env bash
set -euo pipefail

# Release 2 - Azure Container Apps environment and database storage setup.
# Reuses existing infrastructure to protect persistent SQLite data.

RESOURCE_GROUP="${RESOURCE_GROUP:-asd-release2-rg}"

DATABASES=(
  user-database
  assessment-database
  calendar-database
  enrolment-database
  notebook-database
  exam-database
)

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

valid_tag() {
  [[ -n "$1" && "$1" != "None" && "$1" != "null" ]]
}

# Step 1: Verify Azure authentication.

command -v az >/dev/null 2>&1 || fail "Azure CLI is required"
# Select a working Python 3 executable.
# Windows Git Bash may resolve python3 to the Microsoft Store alias.
if command -v python3 >/dev/null 2>&1 &&
   python3 -c 'import sys; sys.exit(sys.version_info.major != 3)' >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1 &&
     python -c 'import sys; sys.exit(sys.version_info.major != 3)' >/dev/null 2>&1; then
  PYTHON=python
else
  fail "A working Python 3 installation is required."
fi

echo "Using Python: $PYTHON"

az account show --output none >/dev/null 2>&1 ||
  fail "Not authenticated to Azure"

# Step 2: Verify the existing resource group.

if ! az group show \
    --name "$RESOURCE_GROUP" \
    --output none; then
  fail "Resource group '$RESOURCE_GROUP' does not exist."
fi

# Step 3: Read the existing infrastructure configuration.

ENV_NAME="$(az group show \
  --name "$RESOURCE_GROUP" \
  --query 'tags.envName' -o tsv)"

LOCATION="$(az group show \
  --name "$RESOURCE_GROUP" \
  --query 'tags.location' -o tsv)"

STORAGE_ACCOUNT="$(az group show \
  --name "$RESOURCE_GROUP" \
  --query 'tags.storageAccountName' -o tsv)"

valid_tag "$ENV_NAME" ||
  fail "Missing envName resource group tag."

valid_tag "$LOCATION" ||
  fail "Missing location resource group tag."

valid_tag "$STORAGE_ACCOUNT" ||
  fail "Missing storageAccountName resource group tag."

[[ "$STORAGE_ACCOUNT" =~ ^[a-z0-9]{3,24}$ ]] ||
  fail "Invalid storage account name: $STORAGE_ACCOUNT"

printf '\n=== Release 2 Container Apps Environment and Storage ===\n'
printf 'Resource group: %s\n' "$RESOURCE_GROUP"
printf 'Environment: %s\n' "$ENV_NAME"
printf 'Storage account: %s\n' "$STORAGE_ACCOUNT"

# Step 4: Verify the existing Container Apps environment.

echo "Checking Container Apps environment: $ENV_NAME"

if ! az containerapp env show \
    --name "$ENV_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --output none; then
  fail "Container Apps environment '$ENV_NAME' does not exist."
fi

STATE="$(az containerapp env show \
  --name "$ENV_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query 'properties.provisioningState' -o tsv)"

[[ "$STATE" == "Succeeded" ]] ||
  fail "Container Apps environment not ready: $STATE"

echo "Container Apps environment verified."

# Step 5: Verify the existing storage account.

echo "Checking storage account: $STORAGE_ACCOUNT"

if ! az storage account show \
    --name "$STORAGE_ACCOUNT" \
    --resource-group "$RESOURCE_GROUP" \
    --output none; then
  fail "Storage account '$STORAGE_ACCOUNT' does not exist."
fi

STORAGE_STATE="$(az storage account show \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --query 'provisioningState' -o tsv)"

[[ "$STORAGE_STATE" == "Succeeded" ]] ||
  fail "Storage account not ready: $STORAGE_STATE"

echo "Storage account verified."

# Step 6: Verify all six Azure Files shares and their registrations.

for DATABASE in "${DATABASES[@]}"; do
  echo "Checking database storage: $DATABASE"

  # Never create a new, empty share during deployment.
  if ! az storage share-rm show \
      --resource-group "$RESOURCE_GROUP" \
      --storage-account "$STORAGE_ACCOUNT" \
      --name "$DATABASE" \
      --output none; then
    fail "Required Azure Files share '$DATABASE' does not exist."
  fi

  echo "  Existing file share verified."

  # Never silently repoint a persistent mount.
  if ! az containerapp env storage show \
      --name "$ENV_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --storage-name "$DATABASE" \
      --output none; then
    fail "Environment storage registration '$DATABASE' does not exist."
  fi

  EXISTING="$(az containerapp env storage show \
    --name "$ENV_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --storage-name "$DATABASE" \
    --output json)"

  if ! EXISTING="$EXISTING" \
      EXPECTED_ACCOUNT="$STORAGE_ACCOUNT" \
      EXPECTED_SHARE="$DATABASE" \
      "$PYTHON" - <<'PY'
import json
import os
import sys

item = json.loads(os.environ["EXISTING"])
azure_file = (item.get("properties") or {}).get("azureFile") or {}

valid = (
    azure_file.get("accessMode") == "ReadWrite"
    and azure_file.get("accountName", "").lower()
        == os.environ["EXPECTED_ACCOUNT"]
    and azure_file.get("shareName") == os.environ["EXPECTED_SHARE"]
)

sys.exit(0 if valid else 1)
PY
  then
    fail "Storage registration '$DATABASE' has an unexpected configuration."
  fi

  echo "  Environment storage registration verified."
done

printf '\n=== Environment Verification Complete ===\n'
printf 'Container Apps environment and all six Azure Files shares verified.\n'
printf 'SQLite databases must write their files under /app/data.\n'