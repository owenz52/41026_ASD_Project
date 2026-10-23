import subprocess
import sys


def test_pip_audit_passes():
    result = subprocess.run(
        [sys.executable, "-m", "pip_audit"],
        capture_output=True,
        text=True,
    )
    returncode = result.returncode  # avoid pytest reprinting the full CompletedProcess in the assert
    assert returncode == 0, result.stdout + result.stderr