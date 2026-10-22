#!/usr/bin/env bash
set -euo pipefail

# Release 2 - Azure Container Apps environment and database storage setup.
# Requires az login (or GitHub Actions azure/login), storage account key access, and permission to manage Azure resources in the resource group.

RESOURCE_GROUP="${RESOURCE_GROUP:-asd-release2-rg}"
STORAGE_SKU="${STORAGE_SKU:-Standard_LRS}"
STORAGE_SHARE_QUOTA_GB="${STORAGE_SHARE_QUOTA_GB:-5}"

DATABASES=(
  user-database
  assessment-database
  calendar-database
  enrolment-database
  notebook-database
  exam-database
)

fail() { echo "ERROR: $*" >&2; exit 1; }
valid_tag() { [[ -n "$1" && "$1" != "None" && "$1" != "null" ]]; }

command -v az >/dev/null 2>&1 || fail "Azure CLI is required"
az account show --output none >/dev/null 2>&1 || fail "Not authenticated to Azure (run az login)"

if [[ "$(az group exists --name "$RESOURCE_GROUP" --output tsv)" != "true" ]]; then
  fail "Resource group $RESOURCE_GROUP does not exist. Run env-setup.sh first."
fi

ENV_NAME="$(az group show --name "$RESOURCE_GROUP" --query 'tags.envName' -o tsv)"
LOCATION="$(az group show --name "$RESOURCE_GROUP" --query 'tags.location' -o tsv)"
valid_tag "$ENV_NAME" || fail "Resource group tag envName missing; run env-setup.sh"
valid_tag "$LOCATION" || fail "Resource group tag location missing; run env-setup.sh"

# Persist generated storage account name in resource group tags to ensure
# subsequent runs reuse the same account and do not risk data loss.
STORAGE_ACCOUNT="$(az group show --name "$RESOURCE_GROUP" --query 'tags.storageAccountName' -o tsv)"
if ! valid_tag "$STORAGE_ACCOUNT"; then
  if [[ -n "${AZURE_STORAGE_ACCOUNT:-}" ]]; then
    STORAGE_ACCOUNT="$AZURE_STORAGE_ACCOUNT"
  else
    # Global uniqueness, lowercase alphanumeric, <=24 chars.
    STORAGE_ACCOUNT="asdr2data$(python -c 'import secrets; print(secrets.token_hex(6))')"
  fi
  [[ "$STORAGE_ACCOUNT" =~ ^[a-z0-9]{3,24}$ ]] || fail "Invalid storage account name: $STORAGE_ACCOUNT"
  az group update --name "$RESOURCE_GROUP" \
    --set "tags.storageAccountName=$STORAGE_ACCOUNT" --output none
fi

[[ "$STORAGE_ACCOUNT" =~ ^[a-z0-9]{3,24}$ ]] || fail "Invalid storage account name: $STORAGE_ACCOUNT"

printf '\n=== Release 2 Container Apps Environment and Storage ===\n'
printf 'Resource group: %s\nEnvironment: %s\nStorage account: %s\n' "$RESOURCE_GROUP" "$ENV_NAME" "$STORAGE_ACCOUNT"

if az containerapp env show --name "$ENV_NAME" --resource-group "$RESOURCE_GROUP" --output none 2>/dev/null; then
  echo 'Reusing Container Apps environment.'
else
  az containerapp env create --name "$ENV_NAME" --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --environment-mode WorkloadProfiles \
    --output none
fi

STATE="$(az containerapp env show --name "$ENV_NAME" --resource-group "$RESOURCE_GROUP" \
  --query 'properties.provisioningState' -o tsv)"
[[ "$STATE" == 'Succeeded' ]] || fail "Container Apps environment not ready: $STATE"

# Do not overwrite an existing storage account or change its security settings.
if az storage account show --name "$STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" --output none 2>/dev/null; then
  echo 'Reusing storage account.'
else
  az storage account create \
    --name "$STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" --sku "$STORAGE_SKU" --kind StorageV2 \
    --https-only true --min-tls-version TLS1_2 \
    --allow-blob-public-access false --output none
fi

# Container Apps Azure Files registration requires a storage account key.
# Never print the key or persist it to the repository or GitHub Actions logs.
ACCOUNT_KEY="$(az storage account keys list --account-name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" --query '[0].value' -o tsv)"
[[ -n "$ACCOUNT_KEY" && "$ACCOUNT_KEY" != 'None' ]] || fail 'Could not retrieve Azure Files credentials'  # pragma: allowlist secret

for DATABASE in "${DATABASES[@]}"; do
  echo "Configuring database storage: $DATABASE"

  if az storage share-rm show --resource-group "$RESOURCE_GROUP" \
      --storage-account "$STORAGE_ACCOUNT" --name "$DATABASE" --output none 2>/dev/null; then
    echo '  Existing file share found.'
  else
    az storage share-rm create \
      --resource-group "$RESOURCE_GROUP" --storage-account "$STORAGE_ACCOUNT" \
      --name "$DATABASE" --quota "$STORAGE_SHARE_QUOTA_GB" \
      --enabled-protocols SMB --output none
    echo '  File share created.'
  fi

  if az containerapp env storage show \
      --name "$ENV_NAME" --resource-group "$RESOURCE_GROUP" \
      --storage-name "$DATABASE" --output none 2>/dev/null; then
    # Avoid silently repointing an existing persistent mount to a new share.
    EXISTING="$(az containerapp env storage show \
      --name "$ENV_NAME" --resource-group "$RESOURCE_GROUP" \
      --storage-name "$DATABASE" --output json)"
    if ! EXISTING="$EXISTING" EXPECTED_ACCOUNT="$STORAGE_ACCOUNT" \
        EXPECTED_SHARE="$DATABASE" python - <<'PY'
import json, os, sys
item = json.loads(os.environ['EXISTING'])
file = (item.get('properties') or {}).get('azureFile') or {}
valid = (
    file.get('accessMode') == 'ReadWrite'
    and file.get('accountName', '').lower() == os.environ['EXPECTED_ACCOUNT']
    and file.get('shareName', '') == os.environ['EXPECTED_SHARE']
)
sys.exit(0 if valid else 1)
PY
    then
      fail "Existing environment storage '$DATABASE' points elsewhere or is not ReadWrite; review manually to protect existing data"
    fi
    echo '  Environment storage registration already correct.'
  else
    az containerapp env storage set \
      --name "$ENV_NAME" --resource-group "$RESOURCE_GROUP" \
      --storage-name "$DATABASE" --access-mode ReadWrite \
      --azure-file-account-name "$STORAGE_ACCOUNT" \
      --azure-file-account-key "$ACCOUNT_KEY" \
      --azure-file-share-name "$DATABASE" --output none
    echo '  Environment storage registered.'
  fi

done

unset ACCOUNT_KEY
printf '\nReady: Container Apps environment and six database Azure Files shares.\n'
printf 'Remember: database code must write its SQLite files under /app/data.\n'
