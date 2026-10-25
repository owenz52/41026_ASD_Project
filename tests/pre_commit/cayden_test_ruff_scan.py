import subprocess
import sys


def test_ruff_scan_passes():
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--output-format=concise", "student-caydenyip"],
        capture_output=True,
        text=True,
    )
    returncode = result.returncode  # avoid pytest reprinting the full CompletedProcess in the assert
    assert returncode == 0, result.stdout + result.stderr