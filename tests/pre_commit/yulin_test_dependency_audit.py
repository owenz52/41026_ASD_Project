import subprocess
import sys

REQUIREMENTS_FILES = [
    "student-yulinzhu/backend/requirements.txt",
    "student-yulinzhu/database/requirements.txt",
]


def test_pip_audit_passes():
    failures = []

    for requirements_file in REQUIREMENTS_FILES:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip_audit",
                "-r",
                requirements_file,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            failures.append(
                f"\nAudit failed for {requirements_file}:\n"
                f"{result.stdout}{result.stderr}"
            )

    assert not failures, "\n".join(failures)