import io
import os
import zipfile

import requests


GITHUB_API = "https://api.github.com"

REPOSITORY = os.getenv(
    "GITHUB_REPOSITORY",
    "owenz52/41026_ASD_Project"
)

TOKEN = os.getenv("GITHUB_TOKEN")


def _headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    return headers


def get_completed_runs(limit=5):
    url = f"{GITHUB_API}/repos/{REPOSITORY}/actions/runs"

    response = requests.get(
        url,
        headers=_headers(),
        params={
            "status": "completed",
            "per_page": limit,
        },
        timeout=30,
    )

    response.raise_for_status()

    return response.json().get("workflow_runs", [])


def get_jobs(run_id):
    url = (
        f"{GITHUB_API}/repos/{REPOSITORY}"
        f"/actions/runs/{run_id}/jobs"
    )

    response = requests.get(
        url,
        headers=_headers(),
        timeout=30,
    )

    response.raise_for_status()

    return response.json().get("jobs", [])


def get_run_logs(run_id, max_chars=12000):
    url = (
        f"{GITHUB_API}/repos/{REPOSITORY}"
        f"/actions/runs/{run_id}/logs"
    )

    response = requests.get(
        url,
        headers=_headers(),
        timeout=30,
    )

    response.raise_for_status()

    archive = zipfile.ZipFile(
        io.BytesIO(response.content)
    )

    log_parts = []

    for filename in archive.namelist():
        if not filename.endswith(".txt"):
            continue

        with archive.open(filename) as file:
            text = file.read().decode(
                "utf-8",
                errors="replace"
            )

        log_parts.append(
            f"\n--- {filename} ---\n{text}"
        )

    logs = "\n".join(log_parts)

    if len(logs) > max_chars:
        logs = (
            logs[:6000]
            + "\n\n[... log output truncated ...]\n\n"
            + logs[-6000:]
        )

    return logs


def build_ci_evidence(run):
    jobs = get_jobs(run["id"])

    lines = [
        f"Workflow: {run.get('name')}",
        f"Run ID: {run.get('id')}",
        f"Branch: {run.get('head_branch')}",
        f"Commit: {run.get('head_sha')}",
        f"Event: {run.get('event')}",
        f"Conclusion: {run.get('conclusion')}",
        f"Created At: {run.get('created_at')}",
        f"Updated At: {run.get('updated_at')}",
        "",
        "Jobs:",
    ]

    for job in jobs:
        lines.append(
            f"- {job.get('name')}: {job.get('conclusion')}"
        )

        for step in job.get("steps", []):
            lines.append(
                f"    - {step.get('name')}: "
                f"{step.get('conclusion')}"
            )

    if run.get("conclusion") != "success":
        try:
            logs = get_run_logs(run["id"])

            if logs:
                lines.extend([
                    "",
                    "Failure Logs:",
                    logs,
                ])

        except requests.HTTPError as error:
            lines.extend([
                "",
                "Failure Logs:",
                f"Unable to retrieve logs: {error}",
            ])

    else:
        lines.extend([
            "",
            "CI Summary:",
            "The workflow completed successfully. "
            "Raw logs were not included because no failed CI stage requires diagnosis.",
        ])

    return "\n".join(lines)