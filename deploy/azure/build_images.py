import argparse
import json
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "deploy/azure/services.json"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--registry", default="", help="Optional registry hostname, without https://",)
    parser.add_argument("--build", action="store_true", help="Execute builds, otherwise only print commands",)
    args = parser.parse_args()

    services = json.loads(MANIFEST.read_text(encoding="utf-8")
                          )["services"]
    registry = args.registry.strip().rstrip("/")
    if registry and ("://" in registry or "/" in registry):
        parser.error("--registry must be a host name")
    commands = []

    for service in services:
        context = ROOT / service["context"]
        dockerfile = context / service["dockerfile"]
        if not dockerfile.is_file():
            raise FileNotFoundError(dockerfile)
        image = f"{service['name']}:{args.tag}"
        if registry:
            image = f"{registry}/{image}"
        commands.append(["docker", "build", "--platform", "linux/amd64", "--tag", image, "--file", str(dockerfile), str(context),])

    for command in commands:
        print(shlex.join(command), flush=True)
        if args.build:
            subprocess.run(command, check=True, cwd=ROOT)

    if args.build:
        print(f"Built {len(commands)} images locally. Nothing pushed")
    else:
        print(f"Dry run passed: {len(commands)} build commands")
        print("No images were built or pushed.")

if __name__ == "__main__":
    main()