"""Cross-platform pre-commit launcher with timestamped test reports."""

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def main() -> int:
    os.chdir(PROJECT_ROOT)

    args = sys.argv[1:]

    # Find the test file supplied to pytest.
    test_file = next(
        (
            Path(arg)
            for arg in args
            if arg.endswith(".py") and not arg.startswith("-")
        ),
        None,
    )

    # Create a timestamped report filename.
    run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    report_dir = PROJECT_ROOT / "reports" / "pre-commit"
    report_dir.mkdir(parents=True, exist_ok=True)

    report_path = (
        report_dir / f"pre-commit-report-{run_timestamp}.txt"
    )

    # Run pytest and capture its output.
    result = subprocess.run(
        [sys.executable, "-m", "pytest", *args],
        capture_output=True,
        text=True,
        check=False,
    )

    # Build the report for this test execution.
    report_section = (
        "\n"
        + "=" * 80
        + "\n"
        + "PRE-COMMIT TEST RESULT\n"
        + "=" * 80
        + "\n"
        + f"Test: {test_file or 'Not specified'}\n"
        + f"Timestamp (UTC): "
        + f"{datetime.now(timezone.utc).isoformat()}\n"
        + f"Exit code: {result.returncode}\n\n"
        + "## Standard output\n"
        + f"{result.stdout}\n"
        + "## Standard error\n"
        + f"{result.stderr}\n"
    )

    # Write the test result to the report file.
    with report_path.open("a", encoding="utf-8") as report_file:
        report_file.write(report_section)

    # Display pytest output in the terminal.
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    print(f"\nReport saved to: {report_path}")

    # Preserve pytest's exit code for pre-commit.
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())