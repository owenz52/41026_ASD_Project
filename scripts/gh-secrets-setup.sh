#!/usr/bin/env bash
set -Eeuo pipefail

# Project GitHub Actions OIDC setup
# Configures the federated credential and GitHub Actions secrets.
# Does NOT grant Azure subscription roles automatically.

export MSYS_NO_PATHCONV=1

APP_DISPLAY_NAME="Project-github-oidc"
EXPECTED_SUBSCRIPTION_ID="4f004dab-3d26-4f85-bfd6-065fd3b81611"
EXPECTED_TENANT_ID="38f98f9c-0f30-4c61-9211-4560f70cb0f4"
EXPECTED_CLIENT_ID="ecd04639-59cb-49ea-bb1d-816d86f1b2aa"
FED_CRED_NAME="project-github-actions"
EXPECTED_REPO="owenz52/41026_ASD_Project"

# Use "legacy" for the traditional GitHub OIDC subject.
# Use "immutable" only if this repository uses GitHub's immutable
# owner/repository ID subject format.
OIDC_SUBJECT_MODE="legacy"

echo "=== GitHub Actions OIDC Setup ==="

# Check required tools.
for cmd in az gh git sed cut; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: Required command not found: $cmd"
        exit 1
    fi
done

# Sign in to the intended Azure tenant.
az login --tenant "$EXPECTED_TENANT_ID" --output none

az account set --subscription "$EXPECTED_SUBSCRIPTION_ID"

SUBSCRIPTION_ID=$(az account show --query id -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)

if [[ "$SUBSCRIPTION_ID" != "$EXPECTED_SUBSCRIPTION_ID" ]]; then
    echo "ERROR: Active Azure subscription does not match."
    exit 1
fi

if [[ "$TENANT_ID" != "$EXPECTED_TENANT_ID" ]]; then
    echo "ERROR: Active Azure tenant does not match."
    exit 1
fi

echo "Azure subscription and tenant verified."

# Preserve the existing GitHub CLI account if already authenticated.
if ! gh auth status >/dev/null 2>&1; then
    gh auth login
fi

# Verify repository and branch.
REPO_URL=$(git remote get-url origin)
REPO_SLUG=$(printf '%s\n' "$REPO_URL" |
    sed -E 's#^(git@github\.com:|https://github\.com/)##; s#\.git$##')
BRANCH=$(git branch --show-current)

if [[ "$REPO_SLUG" != "$EXPECTED_REPO" ]]; then
    echo "ERROR: Unexpected repository: $REPO_SLUG"
    exit 1
fi



# Confirm GitHub can access the repository.
REPO_JSON=$(gh api "repos/$REPO_SLUG")
OWNER_ID=$(printf '%s' "$REPO_JSON" | python -c \
    'import json,sys; print(json.load(sys.stdin)["owner"]["id"])')
REPO_ID=$(printf '%s' "$REPO_JSON" | python -c \
    'import json,sys; print(json.load(sys.stdin)["id"])')

# Confirm the app registration exists in the active tenant.
CLIENT_ID=$(az ad app show \
    --id "$EXPECTED_CLIENT_ID" \
    --query appId -o tsv)

if [[ "$CLIENT_ID" != "$EXPECTED_CLIENT_ID" ]]; then
    echo "ERROR: The expected app registration was not found."
    exit 1
fi

# Ensure its service principal exists in this tenant.
if ! az ad sp show --id "$CLIENT_ID" >/dev/null 2>&1; then
    echo "Creating the app's service principal..."
    az ad sp create --id "$CLIENT_ID" --output none
fi

# Build the GitHub OIDC subject.
if [[ "$OIDC_SUBJECT_MODE" == "immutable" ]]; then
    SUBJECT="repo:owenz52@$OWNER_ID/41026_ASD_Project@$REPO_ID:ref:refs/heads/$BRANCH"
else
    SUBJECT="repo:$REPO_SLUG:ref:refs/heads/$BRANCH"
fi

echo "Repository: $REPO_SLUG"
echo "Branch: $BRANCH"
echo "OIDC subject: $SUBJECT"

# Create or update the federated credential.
FED_CRED_PARAMS=$(printf \
    '{"name":"%s","issuer":"https://token.actions.githubusercontent.com","subject":"%s","description":"GitHub Actions deployment for %s","audiences":["api://AzureADTokenExchange"]}' \
    "$FED_CRED_NAME" "$SUBJECT" "$BRANCH")

EXISTING_FED_CRED=$(az ad app federated-credential list \
    --id "$CLIENT_ID" \
    --query "[?name=='$FED_CRED_NAME'].name | [0]" \
    -o tsv)

if [[ -z "$EXISTING_FED_CRED" || "$EXISTING_FED_CRED" == "None" ]]; then
    az ad app federated-credential create \
        --id "$CLIENT_ID" \
        --parameters "$FED_CRED_PARAMS" \
        --output none
    echo "Created federated credential."
else
    az ad app federated-credential update \
        --id "$CLIENT_ID" \
        --federated-credential-id "$FED_CRED_NAME" \
        --parameters "$FED_CRED_PARAMS" \
        --output none
    echo "Updated federated credential."
fi

# Set GitHub Actions secrets in the intended repository.
gh secret set AZURE_SUBSCRIPTION_ID \
    --repo "$REPO_SLUG" --body "$SUBSCRIPTION_ID"

gh secret set AZURE_TENANT_ID \
    --repo "$REPO_SLUG" --body "$TENANT_ID"

gh secret set AZURE_CLIENT_ID \
    --repo "$REPO_SLUG" --body "$CLIENT_ID"

echo "GitHub Actions secrets configured:"
echo "  AZURE_SUBSCRIPTION_ID"
echo "  AZURE_TENANT_ID"
echo "  AZURE_CLIENT_ID"

echo
echo "NOTE: Azure role assignments have NOT been changed."
echo "You must grant the app only the Azure permissions required"
echo "by your deployment workflow."
echo "=== Setup Complete ==="
