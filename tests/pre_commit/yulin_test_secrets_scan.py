import json
import subprocess
import sys


def test_detect_secrets_scan_passes():
    result = subprocess.run(
        [sys.executable, "-m", "detect_secrets", "scan", "student-yulinzhu"],
        capture_output=True,
        text=True,
    )
    returncode = result.returncode  # avoid pytest reprinting the full CompletedProcess in the assert
    assert returncode == 0, result.stderr
    findings = json.loads(result.stdout)
    assert findings.get("results", {}) == {}, "Potential secrets detected"