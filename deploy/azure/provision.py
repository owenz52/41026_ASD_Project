import argparse
import json
import re
import shlex
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subscription", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute Azure commands and create missing resources",
    )
    args = parser.parse_args()

    if not re.fullmatch(r"[a-z0-9]{5,50}", args.registry):
        parser.error("--registry must contain 5–50 lowercase letters/numbers")

    az = shutil.which("az")
    if args.apply and not az:
        parser.error("Azure CLI is not installed")

    def command(parts):
        return [
            az or "az",
            *parts,
            "--subscription", args.subscription,
            "--only-show-errors",
            "--output", "json",
        ]

    def execute(parts):
        result = subprocess.run(
            command(parts),
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    resources = [
        {
            "kind": "resource group",
            "name": args.resource_group,
            "list": ["group", "list"],
            "create": [
                "group", "create",
                "--name", args.resource_group,
                "--location", args.location,
            ],
        },
        {
            "kind": "container registry",
            "name": args.registry,
            "list": [
                "acr", "list",
                "--resource-group", args.resource_group,
            ],
            "create": [
                "acr", "create",
                "--resource-group", args.resource_group,
                "--name", args.registry,
                "--location", args.location,
                "--sku", "Basic",
                "--admin-enabled", "false",
            ],
        },
        {
            "kind": "Container Apps environment",
            "name": args.environment,
            "list": [
                "containerapp", "env", "list",
                "--resource-group", args.resource_group,
            ],
            "create": [
                "containerapp", "env", "create",
                "--resource-group", args.resource_group,
                "--name", args.environment,
                "--location", args.location,
                "--logs-destination", "log-analytics",
            ],
        },
    ]

    if not args.apply:
        for resource in resources:
            print(f"\nCreate if missing: {resource['kind']}")
            print(shlex.join(command(resource["create"])))

        print("\nPreview complete. No Azure commands were executed.")
        return

    account = execute(["account", "show"])
    if account.get("state") != "Enabled":
        raise RuntimeError("The selected Azure subscription is not enabled")

    print(
        f"Subscription: {account['name']} ({account['id']})",
        flush=True,
    )

    for namespace in (
        "Microsoft.App",
        "Microsoft.ContainerRegistry",
        "Microsoft.OperationalInsights",
    ):
        provider = execute([
            "provider", "show",
            "--namespace", namespace,
        ])
        if provider.get("registrationState") != "Registered":
            raise RuntimeError(
                f"{namespace} is not registered. Ask the subscription "
                "administrator to register it, then rerun."
            )

    for resource in resources:
        existing = next(
            (
                item for item in execute(resource["list"])
                if item["name"].lower() == resource["name"].lower()
            ),
            None,
        )
        if existing:
            location = existing.get("location", "")
            if location.lower() != args.location.lower():
                raise RuntimeError(
                    f"{resource['name']} exists in {location}, "
                    f"but {args.location} was requested"
                )
            print(
                f"Reusing {resource['kind']}: {resource['name']}",
                flush=True,
            )
        else:
            print(
                f"Creating {resource['kind']}: {resource['name']}",
                flush=True,
            )
            execute(resource["create"])

    print("\nFoundation resources ready.")
    print("Existing resource settings were not modified.")
    print("Application deployment, storage and image access are separate steps.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(error.stderr or str(error))
        raise SystemExit(error.returncode)
    except (RuntimeError, ValueError, OSError) as error:
        print(f"ERROR: {error}")
        raise SystemExit(1)