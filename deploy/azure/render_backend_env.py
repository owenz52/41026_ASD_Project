import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

DIRECTORY = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--hosts",
        required=True,
        help="JSON file mapping service names to hostnames",
    )
    args = parser.parse_args()
    config = json.loads(
        (DIRECTORY / "backend-config.json").read_text(encoding="utf-8")
    )
    hosts = json.loads(
        Path(args.hosts).read_text(encoding="utf-8")
    )
    result = {}

    for name, settings in config["backends"].items():
        environment = {}
        if settings["feature_backend"]:
            environment.update(config["feature_defaults"])
        for variable, target in settings["service_urls"].items():
            host = hosts.get(target)
            if not isinstance(host, str) or not host:
                raise ValueError(f"Missing hostname for {target}")
            parsed = urlsplit(f"https://{host}")
            if (
                parsed.hostname != host
                or parsed.netloc != host
                or parsed.path
                or parsed.query
                or parsed.fragment
                or any(character.isspace() for character in host)
            ):
                raise ValueError(
                    f"{target}: use a hostname without scheme, port or path"
                )

            environment[variable] = f"https://{host}"
        result[name] = environment
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main() 