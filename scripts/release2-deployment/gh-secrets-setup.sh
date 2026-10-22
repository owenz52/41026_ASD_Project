
#!/bin/bash
set -e

# One-time, local-only:
# - creates the Azure OIDC app registration (if missing)
# - configures GitHub Actions authentication with Azure using OIDC
# - pushes its identifiers to GitHub Actions secrets.
#
# Release 2 configuration:
# Resource group: asd-release2-rg
# Region: australiaeast
# Registry and Container Apps environment names come from resource group tags.

# Prevents Git Bash on Windows from rewriting --scope "/subscriptions/..." into a local file path.
export MSYS_NO_PATHCONV=1

APP_DISPLAY_NAME="asd-release2-github-oidc"
FED_CRED_NAME="asd-release2-github-actions"
RESOURCE_GROUP="asd-release2-rg"
LOCATION="australiaeast"

echo "=== Release 2 GitHub Secrets Setup ==="

az login

if ! gh auth status >/dev/null 2>&1; then
    gh auth login
fi

echo "Logged in to Azure and GitHub."

REPO_URL=$(git config --get remote.origin.url)
REPO_SLUG=$(echo "$REPO_URL" | sed -E 's#(git@github.com:|https://github.com/)##; s#\.git$##')
BRANCH=$(git rev-parse --abbrev-ref HEAD)

SUBSCRIPTION_ID=$(az account show --query id -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)

if [ -z "$SUBSCRIPTION_ID" ] || [ "$SUBSCRIPTION_ID" = "None" ]; then
    echo "No active subscription found on the current Azure login."
    echo "Run 'az account list --output table' to see available subscriptions, then 'az account set --subscription <id>' and re-run this script."
    exit 1
fi

# Read shared infrastructure configuration from resource group tags.
if ! az group show --name "$RESOURCE_GROUP" >/dev/null 2>&1; then
    echo "Resource group '$RESOURCE_GROUP' does not exist or is inaccessible."
    echo "Run the Release 2 infrastructure setup first."
    exit 1
fi

REGISTRY_NAME=$(az group show \
    --name "$RESOURCE_GROUP" \
    --query "tags.registryName" -o tsv)

ENV_NAME=$(az group show \
    --name "$RESOURCE_GROUP" \
    --query "tags.envName" -o tsv)

if [ -z "$REGISTRY_NAME" ] || [ "$REGISTRY_NAME" = "None" ]; then
    echo "Missing resource group tag: registryName"
    exit 1
fi

if [ -z "$ENV_NAME" ] || [ "$ENV_NAME" = "None" ]; then
    echo "Missing resource group tag: envName"
    exit 1
fi

echo "Resource group: $RESOURCE_GROUP"
echo "Region: $LOCATION"
echo "Container registry: $REGISTRY_NAME"
echo "Container Apps environment: $ENV_NAME"

CLIENT_ID=$(az ad app list \
    --display-name "$APP_DISPLAY_NAME" \
    --query "[0].appId" -o tsv)

if [ -z "$CLIENT_ID" ] || [ "$CLIENT_ID" = "None" ]; then
    echo "No app registration named '$APP_DISPLAY_NAME' found. Creating it..."
    CLIENT_ID=$(az ad app create \
        --display-name "$APP_DISPLAY_NAME" \
        --query appId -o tsv)
    az ad sp create --id "$CLIENT_ID"
    echo "Created app registration."
else
    echo "Found existing app registration '$APP_DISPLAY_NAME'."
fi

echo "Fetched subscription ID, tenant ID, and client ID from Azure."

# Re-sync the federated credential on every run so changes to the
# repository or branch do not leave the credential pointing at an
# outdated subject.
#
# This uses the standard GitHub branch subject format. If the repository
# is configured to use an immutable-ID subject format, this must be
# changed to match the actual subject emitted by GitHub Actions.

SUBJECT="repo:${REPO_SLUG}:ref:refs/heads/${BRANCH}"

FED_CRED_PARAMS="{\"name\":\"${FED_CRED_NAME}\",\"issuer\":\"https://token.actions.githubusercontent.com\",\"subject\":\"${SUBJECT}\",\"audiences\":[\"api://AzureADTokenExchange\"]}"

EXISTING_FED_CRED=$(az ad app federated-credential list \
    --id "$CLIENT_ID" \
    --query "[?name=='$FED_CRED_NAME'].name | [0]" \
    -o tsv 2>/dev/null || true)

if [ -z "$EXISTING_FED_CRED" ] || [ "$EXISTING_FED_CRED" = "None" ]; then
    az ad app federated-credential create \
        --id "$CLIENT_ID" \
        --parameters "$FED_CRED_PARAMS"
    echo "Created federated credential with subject '$SUBJECT'."
else
    az ad app federated-credential update \
        --id "$CLIENT_ID" \
        --federated-credential-id "$FED_CRED_NAME" \
        --parameters "$FED_CRED_PARAMS"
    echo "Synced federated credential to subject '$SUBJECT'."
fi

# Assign Contributor at the project resource group scope, not the
# entire subscription. This still requires authorization to create
# Azure role assignments.
RESOURCE_GROUP_ID=$(az group show \
    --name "$RESOURCE_GROUP" \
    --query id -o tsv)

EXISTING_CONTRIBUTOR=$(az role assignment list \
    --assignee "$CLIENT_ID" \
    --role "Contributor" \
    --scope "$RESOURCE_GROUP_ID" \
    --query "[0].id" -o tsv 2>/dev/null || true)

if [ -z "$EXISTING_CONTRIBUTOR" ] || [ "$EXISTING_CONTRIBUTOR" = "None" ]; then
    az role assignment create \
        --assignee "$CLIENT_ID" \
        --role Contributor \
        --scope "$RESOURCE_GROUP_ID"
    echo "Granted Contributor role at resource group scope."
else
    echo "Contributor role already assigned at resource group scope."
fi

# AcrPull allows the deployment identity to pull images from the registry.
# This is separate from permission to create role assignments.
REGISTRY_ID=$(az acr show \
    --name "$REGISTRY_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query id -o tsv)

EXISTING_ACRPULL=$(az role assignment list \
    --assignee "$CLIENT_ID" \
    --role "AcrPull" \
    --scope "$REGISTRY_ID" \
    --query "[0].id" -o tsv 2>/dev/null || true)

if [ -z "$EXISTING_ACRPULL" ] || [ "$EXISTING_ACRPULL" = "None" ]; then
    az role assignment create \
        --assignee "$CLIENT_ID" \
        --role "AcrPull" \
        --scope "$REGISTRY_ID"
    echo "Granted AcrPull role at registry scope."
else
    echo "AcrPull role already assigned."
fi

# User Access Administrator is deliberately NOT granted automatically.
# If deployment needs to create role assignments, an authorized Azure
# administrator should configure the required permissions separately.

gh secret set AZURE_SUBSCRIPTION_ID --body "$SUBSCRIPTION_ID"
gh secret set AZURE_TENANT_ID --body "$TENANT_ID"
gh secret set AZURE_CLIENT_ID --body "$CLIENT_ID"

echo "Pushed AZURE_SUBSCRIPTION_ID, AZURE_TENANT_ID, and AZURE_CLIENT_ID to GitHub Actions secrets."

echo "=== Release 2 GitHub Secrets Setup Complete ==="
