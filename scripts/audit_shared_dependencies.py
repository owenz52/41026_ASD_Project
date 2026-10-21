import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIREMENTS = [
    "ai-services/agentic-loop/requirements.txt",
    "ai-services/mcp-server/requirements.txt",
    "ai-services/multi-agent-server/requirements.txt",
    "ai-services/rag-server/requirements.txt",
    "shared/backend/requirements.txt",
    "shared/database/requirements.txt",
]

RAG_EXCEPTIONS = [
    "PYSEC-2026-311",
    "PYSEC-2026-3813",
    "PYSEC-2026-3814",
    "PYSEC-2026-3815",
]


def main():
    failed = []

    for relative_path in REQUIREMENTS:
        requirements = ROOT / relative_path

        print(f"\nAuditing: {relative_path}", flush=True)

        command = [
            sys.executable,
            "-m",
            "pip_audit",
            "-r",
            str(requirements),
        ]

        if relative_path == "ai-services/rag-server/requirements.txt":
            print(
                "Applying documented RAG vulnerability exceptions:",
                flush=True,
            )

            for vulnerability_id in RAG_EXCEPTIONS:
                print(f" - {vulnerability_id}", flush=True)
                command.extend([
                    "--ignore-vuln",
                    vulnerability_id,
                ])

        result = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
        )

        if result.returncode != 0:
            failed.append(relative_path)
            print(
                f"FAILED: {relative_path}",
                flush=True,
            )
        else:
            print(
                f"PASSED: {relative_path}",
                flush=True,
            )

    if failed:
        print("\nDependency audit failed:")

        for path in failed:
            print(f" - {path}")

        return 1

    print("\nAll shared dependency audits passed.")
    print(
        "Note: Documented ChromaDB risk exceptions "
        "remain unresolved."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())