```bash
#!/bin/bash
set -euo pipefail

# Deletes the project Azure resource group and all resources inside it.
# WARNING: This permanently deletes resources and may delete stored data.

RESOURCE_GROUP="${RESOURCE_GROUP:-project-rg}"

echo "=== Project Azure Cleanup ==="

# Step 1: Check Azure CLI and login
if ! command -v az >/dev/null 2>&1; then
  echo "ERROR: Azure CLI (az) is not installed or is not on PATH." >&2
  exit 1
fi

if ! az account show >/dev/null 2>&1; then
  echo "ERROR: You are not logged in to Azure. Run: az login" >&2
  exit 1
fi

# Step 2: Check whether the resource group exists
if ! az group show --name "$RESOURCE_GROUP" >/dev/null 2>&1; then
  echo "Resource group '$RESOURCE_GROUP' was not found or is inaccessible."
  echo "Nothing to clean up."
  exit 0
fi

# Step 3: Read project resource names
REGISTRY_NAME="${REGISTRY_NAME:-projectregistry001}"
ENV_NAME="${ENV_NAME:-project-env-001}"

echo
echo "Resources configured for this project:"
echo "  Resource Group:       $RESOURCE_GROUP"
echo "  Container Registry:   $REGISTRY_NAME"
echo "  Container Apps Env:   $ENV_NAME"
echo "  Portal App:           project-portal"
echo "  Backend Apps:         Auth, Assessment, Calendar, Enrolment, Notebook, Exam"
echo "  Database Apps:        User, Assessment, Calendar, Enrolment, Notebook, Exam"
echo "  Student Frontends:    Assessment, Calendar, Enrolment, Notebook, Exam"

echo
echo "WARNING: This deletes EVERYTHING inside '$RESOURCE_GROUP'."
echo "This may include container images, running apps, databases, and stored data."
echo "This action cannot be undone."

# Step 4: Require explicit confirmation outside CI
if [[ -z "${CI:-}" ]]; then
  read -r -p "Type the resource group name to confirm deletion: " CONFIRM

  if [[ "$CONFIRM" != "$RESOURCE_GROUP" ]]; then
    echo "Confirmation did not match. Aborting." >&2
    exit 1
  fi
else
  echo "CI environment detected; refusing to delete resources automatically." >&2
  echo "Run this script manually to confirm deletion." >&2
  exit 1
fi

# Step 5: Delete the resource group
echo
echo "Starting deletion of resource group '$RESOURCE_GROUP'..."

az group delete \
  --name "$RESOURCE_GROUP" \
  --yes \
  --no-wait

echo
echo "=== Deletion Started ==="
echo "Azure is deleting resource group '$RESOURCE_GROUP' in the background."
echo
echo "To check whether the resource group still exists, run:"
echo "  az group show --name \"$RESOURCE_GROUP\""
echo
echo "To list remaining resource groups, run:"
echo "  az group list --output table"
```