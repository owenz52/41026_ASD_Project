#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

export RESOURCE_GROUP="${RESOURCE_GROUP:-asd-release2-rg}"
: "${IMAGE_TAG:?Set IMAGE_TAG to the tag used when building images}"
export IMAGE_TAG

command -v az >/dev/null || {
    echo "ERROR: Azure CLI is required." >&2
    exit 1
}

command -v python3 >/dev/null || {
    echo "ERROR: Python 3 is required." >&2
    exit 1
}

# Provision or reuse a dedicated identity for Container Apps image pulls.
# This is intentionally separate from the GitHub OIDC deployment identity.
IDENTITY_NAME="${ACR_PULL_IDENTITY_NAME:-asd-r2-acr-pull}"
REGISTRY_NAME="$(az group show --name "$RESOURCE_GROUP" --query 'tags.registryName' -o tsv)"
if [[ -z "$REGISTRY_NAME" || "$REGISTRY_NAME" == "None" ]]; then
    echo "ERROR: Resource group is missing registryName tag. Run env-setup.sh first." >&2
    exit 1
fi
REGISTRY_ID="$(az acr show --name "$REGISTRY_NAME" --resource-group "$RESOURCE_GROUP" --query id -o tsv)"
REGISTRY_MODE="$(az acr show --name "$REGISTRY_NAME" --resource-group "$RESOURCE_GROUP" --query roleAssignmentMode -o tsv)"

if [[ -z "${ACR_PULL_IDENTITY_ID:-}" ]]; then
    if ! az identity show --name "$IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" -o none 2>/dev/null; then
        echo "Creating ACR pull identity: $IDENTITY_NAME"
        az identity create --name "$IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" \
            --location "${LOCATION:-australiaeast}" -o none
    fi
    ACR_PULL_IDENTITY_ID="$(az identity show --name "$IDENTITY_NAME" \
        --resource-group "$RESOURCE_GROUP" --query id -o tsv)"
fi
IDENTITY_PRINCIPAL_ID="$(az identity show --ids "$ACR_PULL_IDENTITY_ID" --query principalId -o tsv)"
if [[ -z "$IDENTITY_PRINCIPAL_ID" || "$IDENTITY_PRINCIPAL_ID" == "None" ]]; then
    echo "ERROR: The managed identity has no principal ID." >&2
    exit 1
fi

case "$REGISTRY_MODE" in
    rbac-abac)
        PULL_ROLE="Container Registry Repository Reader"
        ;;
    rbac|LegacyRegistryPermissions|None|"")
        PULL_ROLE="AcrPull"
        ;;
    *)
        echo "ERROR: Unknown ACR role assignment mode: $REGISTRY_MODE" >&2
        exit 1
        ;;
esac

ASSIGNMENT_COUNT="$(az role assignment list \
    --assignee "$IDENTITY_PRINCIPAL_ID" --scope "$REGISTRY_ID" \
    --role "$PULL_ROLE" --query 'length(@)' -o tsv)"

if [[ "$ASSIGNMENT_COUNT" == "0" ]]; then
    echo "ERROR: Managed identity is missing the $PULL_ROLE role on ACR." >&2
    echo "Assign this role using an Azure account with role-assignment permissions before deployment." >&2
    exit 1
fi

export ACR_PULL_IDENTITY_ID
printf 'ACR identity ready: %s (role: %s)\n' "$ACR_PULL_IDENTITY_ID" "$PULL_ROLE"

python3 - <<'PY'
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path.cwd()
GROUP = os.environ["RESOURCE_GROUP"]
TAG = os.environ["IMAGE_TAG"]
IDENTITY = os.environ["ACR_PULL_IDENTITY_ID"]

def az(*arguments):
    result = subprocess.run(
        ["az", *arguments, "--only-show-errors", "-o", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout) if result.stdout.strip() else {}

def require(value, description):
    if not value or value == "None":
        raise ValueError(f"Missing {description}")
    return value

def deployment_order(service):
    name = service["name"]
    if name.endswith("-database"):
        return 0
    if name.endswith("-backend"):
        return 1
    if name == "portal-frontend":
        return 3
    return 2

def deploy():
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", TAG):
        raise ValueError("Invalid IMAGE_TAG")
    services = json.loads(
        (ROOT / "deploy/azure/services.json").read_text()
    )["services"]
    backend_config = json.loads(
        (ROOT / "deploy/azure/backend-config.json").read_text()
    )
    names = {service["name"] for service in services}
    databases = {name for name in names if name.endswith("-database")}
    backends = {name for name in names if name.endswith("-backend")}
    if len(services) != 18 or len(names) != 18:
        raise ValueError("Expected 18 uniquely named services")
    if len(databases) != 6 or len(backends) != 6:
        raise ValueError("Expected six databases and six backends")
    if set(backend_config["backends"]) != backends:
        raise ValueError("backend-config.json does not match services.json")
    for service in services:
        if not re.fullmatch(r"[a-z][a-z0-9-]*", service["name"]):
            raise ValueError(f"Invalid name: {service['name']}")
        if type(service["port"]) is not int:
            raise ValueError("Service ports must be integers")
        if not 1 <= service["port"] <= 65535:
            raise ValueError("Service port out of range")
        if type(service["external"]) is not bool:
            raise ValueError("external must be a boolean")
    public = [s["name"] for s in services if s["external"]]
    if public != ["portal-frontend"]:
        raise ValueError("Only portal-frontend may be public")
    flags = backend_config["feature_defaults"]
    for flag in (
        "AI_ENABLED", "MCP_ENABLED",
        "RAG_ENABLED", "MULTI_AGENT_ENABLED",
    ):
        if flags.get(flag) != "false":
            raise ValueError(f"{flag} must default to false")
    for settings in backend_config["backends"].values():
        for target in settings["service_urls"].values():
            if target not in names:
                raise ValueError(f"Unknown dependency: {target}")
    account = az("account", "show")
    print(f"Subscription: {account['name']} ({account['id']})", flush=True)
    group = az("group", "show", "--name", GROUP)
    tags = group.get("tags") or {}
    registry_name = require(tags.get("registryName"), "registryName tag")
    environment_name = require(tags.get("envName"), "envName tag")
    registry = az(
        "acr", "show",
        "--name", registry_name,
        "--resource-group", GROUP,
    )
    server = require(registry.get("loginServer"), "ACR login server")
    environment = az(
        "containerapp", "env", "show",
        "--name", environment_name,
        "--resource-group", GROUP,
    )
    environment_id = environment["id"]

    identity = az("identity", "show", "--ids", IDENTITY)
    identity_id = identity["id"]

    # Each database must have its own preconfigured ReadWrite file share.
    # This checks registration, not filesystem reliability or database health.
    for name in sorted(databases):
        storage = az(
            "containerapp", "env", "storage", "show",
            "--name", environment_name,
            "--resource-group", GROUP,
            "--storage-name", name,
        )
        file_share = storage.get("properties", {}).get("azureFile", {})
        if file_share.get("accessMode") != "ReadWrite":
            raise ValueError(f"Missing ReadWrite Azure Files storage: {name}")
    existing_names = {
        app["name"]
        for app in az("containerapp", "list", "--resource-group", GROUP)
    }
    hosts = {}
    with tempfile.TemporaryDirectory() as directory:
        for service in sorted(services, key=deployment_order):
            name = service["name"]
            is_database = name in databases
            if name in existing_names:
                current = az(
                    "containerapp", "show",
                    "--name", name,
                    "--resource-group", GROUP,
                )
                properties = current["properties"]
                current_environment = (
                    properties.get("environmentId")
                    or properties.get("managedEnvironmentId")
                )
                if (
                    current_environment
                    and current_environment.lower() != environment_id.lower()
                ):
                    raise ValueError(f"{name} belongs to another environment")
                configuration = properties.get("configuration") or {}
                template = properties.get("template") or {}
                identity_config = current.get("identity") or {}
            else:
                configuration = {}
                template = {}
                identity_config = {}
            containers = template.get("containers", [])
            if len(containers) > 1:
                raise ValueError(f"{name}: review multi-container app manually")
            container = containers[0] if containers else {}
            variables = {}
            if is_database:
                variables["DATA_DIR"] = "/app/data"
            if name in backends:
                settings = backend_config["backends"][name]
                if settings["feature_backend"]:
                    variables.update(flags)
                for variable, target in settings["service_urls"].items():
                    if target not in hosts:
                        raise ValueError(f"{name}: dependency not ready: {target}")
                    variables[variable] = f"https://{hosts[target]}"
            if name == "portal-frontend":
                for target, hostname in hosts.items():
                    if target.endswith(("-backend", "-frontend")):
                        variable = target.upper().replace("-", "_") + "_HOST"
                        variables[variable] = hostname
            env = {
                entry["name"]: entry
                for entry in container.get("env", [])
            }
            for key, value in variables.items():
                env[key] = {"name": key, "value": value}

            container.update({
                "name": name,
                "image": f"{server}/{name}:{TAG}",
                "resources": {"cpu": 0.5, "memory": "1Gi"},
                "env": list(env.values()),
            })
            if is_database:
                mounts = [
                    item for item in container.get("volumeMounts", [])
                    if item["mountPath"] != "/app/data"
                    and item["volumeName"] != "database-data"
                ]
                mounts.append({
                    "volumeName": "database-data",
                    "mountPath": "/app/data",
                })
                container["volumeMounts"] = mounts
                volumes = [
                    item for item in template.get("volumes", [])
                    if item["name"] != "database-data"
                ]
                volumes.append({
                    "name": "database-data",
                    "storageType": "AzureFile",
                    "storageName": name,
                })
                template["volumes"] = volumes
            template.pop("revisionSuffix", None)
            template["containers"] = [container]
            template["scale"] = {
                "minReplicas": 1,
                "maxReplicas": 1,
            }
            configuration["activeRevisionsMode"] = "Single"
            configuration["ingress"] = {
                "external": service["external"],
                "targetPort": service["port"],
                "transport": "auto",
                "allowInsecure": False,
                "traffic": [{"latestRevision": True, "weight": 100}],
            }
            registries = [
                item for item in configuration.get("registries", [])
                if item.get("server") != server
            ]
            registries.append({"server": server, "identity": identity_id})
            configuration["registries"] = registries
            old_type = identity_config.get("type", "")
            identity_config["type"] = (
                "SystemAssigned, UserAssigned"
                if "SystemAssigned" in old_type
                else "UserAssigned"
            )
            identity_config.setdefault(
                "userAssignedIdentities", {}
            )[identity_id] = {}
            identity_config.pop("principalId", None)
            identity_config.pop("tenantId", None)
            document = {
                "name": name,
                "location": environment["location"],
                "identity": identity_config,
                "properties": {
                    "managedEnvironmentId": environment_id,
                    "configuration": configuration,
                    "template": template,
                },
            }
            path = Path(directory) / f"{name}.yaml"
            path.write_text(json.dumps(document, indent=2))
            action = "update" if name in existing_names else "create"
            print(f"{action.upper()}: {name}", flush=True)
            az(
                "containerapp", action,
                "--name", name,
                "--resource-group", GROUP,
                "--yaml", str(path),
            )
            deployed = az(
                "containerapp", "show",
                "--name", name,
                "--resource-group", GROUP,
            )
            properties = deployed["properties"]
            if properties.get("provisioningState") != "Succeeded":
                raise RuntimeError(f"Provisioning failed: {name}")
            hosts[name] = require(
                properties.get("configuration", {}).get("ingress", {}).get("fqdn"),
                f"{name} FQDN",
            )
    print("\n=== Container App Provisioning Complete ===")
    print(f"Processed: {len(hosts)} applications")
    print(f"Image tag: {TAG}")
    print(f"Frontend URL: https://{hosts['portal-frontend']}")
    print("Health, CRUD and persistence verification are still required.")

try:
    deploy()
except subprocess.CalledProcessError as error:
    print(error.stderr or str(error))
    raise SystemExit(error.returncode)
except (ValueError, RuntimeError, OSError, KeyError) as error:
    print(f"ERROR: {error}")
    raise SystemExit(1)
PY