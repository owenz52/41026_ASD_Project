"""Collect real Release 2 testing evidence instead of trusting supplied results.

Pre-commit evidence comes from executing the shared security hooks defined in
.pre-commit-config.yaml. Post-commit evidence comes from the GitHub Actions
endpoint-test steps of each student workflow.
"""

import os
import re
import shutil
import subprocess  # noqa: S404 - fixed commands only, never user input
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from github_client import GITHUB_API, REPOSITORY, _headers


REPO_ROOT = Path(
    os.getenv("REPO_ROOT", str(Path(__file__).resolve().parents[3]))
)

# Review check name -> pre-commit hook id in .pre-commit-config.yaml
PRECOMMIT_HOOKS = {
    "ruff": "ruff-release2",
    "detect_secrets": "detect-secrets",
    "pip_audit": "pip-audit-shared",
}

PRECOMMIT_TIMEOUT = int(os.getenv("PRECOMMIT_TIMEOUT", "300"))

# Matches "Test Assessment Tracker endpoints", "Test Enrolment endpoint
# functions", "Run pytest", but not "Install pytest" or "Upload endpoint test
# evidence".
TEST_STEP_PATTERN = re.compile(
    os.getenv(
        "CI_TEST_STEP_PATTERN",
        r"^(test|run)\b.*\b(endpoint|unit|pytest)",
    ),
    re.IGNORECASE,
)

OUTPUT_TAIL_LINES = 25


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def _tail(text, lines=OUTPUT_TAIL_LINES):
    kept = [line for line in text.strip().splitlines() if line.strip()]
    return "\n".join(kept[-lines:])


def _git(*args):
    git = shutil.which("git")

    if git is None:
        return None

    result = subprocess.run(  # noqa: S603 - fixed git arguments
        [git, *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    return result.stdout.strip() if result.returncode == 0 else None


def repository_state():
    status = _git("status", "--porcelain", "--untracked-files=no")

    return {
        "commit": _git("rev-parse", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "uncommitted_changes": bool(status) if status is not None else None,
    }


def _precommit_command():
    executable = shutil.which("pre-commit")

    if executable:
        return [executable]

    return [sys.executable, "-m", "pre_commit"]


def run_precommit_hook(check_name, hook_id):
    """Execute one pre-commit hook and record what actually happened."""

    command = [
        *_precommit_command(),
        "run",
        hook_id,
        "--all-files",
        "--color",
        "never",
    ]

    record = {
        "status": "error",
        "executed": False,
        "source": "pre-commit",
        "hook_id": hook_id,
        "command": f"pre-commit run {hook_id} --all-files",
        "executed_at": timestamp(),
    }

    started = time.monotonic()

    try:
        result = subprocess.run(  # noqa: S603 - hook ids are fixed constants
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=PRECOMMIT_TIMEOUT,
            check=False,
        )
    except FileNotFoundError:
        record["error"] = "pre-commit is not installed"
        return record
    except subprocess.TimeoutExpired:
        record["executed"] = True
        record["error"] = f"Timed out after {PRECOMMIT_TIMEOUT} seconds"
        return record

    output = (result.stdout or "") + (result.stderr or "")

    record["executed"] = True
    record["exit_code"] = result.returncode
    record["duration_seconds"] = round(time.monotonic() - started, 2)

    if result.returncode == 0:
        record["status"] = "pass"
        record["output"] = _tail(output, 5)
    elif "No module named pre_commit" in output:
        record["executed"] = False
        record["error"] = "pre-commit is not installed"
    else:
        record["status"] = "fail"
        record["output"] = _tail(output)

    return record


def collect_precommit_checks():
    return {
        check_name: run_precommit_hook(check_name, hook_id)
        for check_name, hook_id in PRECOMMIT_HOOKS.items()
    }


def _github_get(path, params=None):
    """GET from the GitHub API, retrying anonymously if a token is rejected.

    The project repository is public, so an expired local token should not
    prevent evidence collection.
    """

    url = f"{GITHUB_API}/repos/{REPOSITORY}{path}"
    headers = _headers()

    response = requests.get(url, headers=headers, params=params, timeout=30)

    if response.status_code == 401 and "Authorization" in headers:
        headers = {
            key: value
            for key, value in headers.items()
            if key != "Authorization"
        }
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json(), "GitHub token rejected; used anonymous access"

    response.raise_for_status()

    return response.json(), None


def default_student_workflows():
    workflow_dir = REPO_ROOT / ".github" / "workflows"
    return sorted(path.name for path in workflow_dir.glob("student-*.yml"))


def collect_workflow_tests(workflow_file, branch="main"):
    """Summarise endpoint-test steps from the latest completed workflow run."""

    record = {
        "workflow": workflow_file,
        "branch": branch,
        "status": "missing",
    }

    try:
        data, warning = _github_get(
            f"/actions/workflows/{workflow_file}/runs",
            {"branch": branch, "status": "completed", "per_page": 1},
        )
    except requests.RequestException as exc:
        record["error"] = f"Could not query GitHub Actions: {exc}"
        return record

    if warning:
        record["warning"] = warning

    runs = data.get("workflow_runs", [])

    if not runs:
        record["error"] = f"No completed run found on branch {branch}"
        return record

    run = runs[0]

    record.update({
        "run_id": run.get("id"),
        "run_url": run.get("html_url"),
        "commit": run.get("head_sha"),
        "event": run.get("event"),
        "run_conclusion": run.get("conclusion"),
        "completed_at": run.get("updated_at"),
    })

    try:
        jobs_data, _ = _github_get(f"/actions/runs/{run['id']}/jobs")
    except requests.RequestException as exc:
        record["error"] = f"Could not read workflow jobs: {exc}"
        return record

    test_steps = [
        {
            "job": job.get("name"),
            "step": step.get("name"),
            "conclusion": step.get("conclusion"),
        }
        for job in jobs_data.get("jobs", [])
        for step in job.get("steps", [])
        if TEST_STEP_PATTERN.search(step.get("name") or "")
    ]

    record["test_steps"] = test_steps

    if not test_steps:
        record["error"] = "No endpoint test step found in the latest run"
        return record

    conclusions = {step["conclusion"] for step in test_steps}

    record["status"] = "pass" if conclusions == {"success"} else "fail"

    return record


def collect_ci_tests(workflows=None, branch="main"):
    """Aggregate post-commit endpoint tests across student workflows."""

    workflows = workflows or default_student_workflows()

    results = [
        collect_workflow_tests(workflow, branch)
        for workflow in workflows
    ]

    statuses = {result["status"] for result in results}

    if statuses == {"pass"}:
        status = "pass"
    elif "fail" in statuses:
        status = "fail"
    else:
        status = "missing"

    return {
        "status": status,
        "executed": any(result.get("test_steps") for result in results),
        "source": "github-actions",
        "workflows_checked": len(results),
        "workflows_passing": sum(r["status"] == "pass" for r in results),
        "workflows": results,
    }


def collect_testing_evidence(workflows=None, branch="main"):
    checks = collect_precommit_checks()
    checks["pytest"] = collect_ci_tests(workflows, branch)

    return {
        "source": "collected",
        "collected_at": timestamp(),
        "repository": repository_state(),
        "checks": checks,
    }
