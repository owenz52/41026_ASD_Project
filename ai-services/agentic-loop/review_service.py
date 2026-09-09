from datetime import datetime, timezone
from pathlib import Path

from github_client import get_completed_runs, build_ci_evidence
from llm_client import generate
from state_store import load_reviewed_runs, save_reviewed_runs


BASE_DIR = Path(__file__).parent
PROMPTS_DIR = BASE_DIR / "prompts"
REPORTS_DIR = BASE_DIR / "reports"


def load_prompt(filename):
    return (PROMPTS_DIR / filename).read_text(
        encoding="utf-8"
    )


def has_required_sections(review):
    required_sections = [
        "## PLAN",
        "## ACT",
        "## OBSERVE",
        "## ADAPT",
    ]

    review_upper = review.upper()

    return all(
        section in review_upper
        for section in required_sections
    )


def save_report(run, evidence, review):
    REPORTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d-%H%M%SZ")

    report_path = (
        REPORTS_DIR
        / f"ci-review-{run['id']}-{timestamp}.md"
    )

    content_lines = [
        "# Shared Agentic DevOps Review",
        "",
        "## Workflow Information",
        "",
        f"Workflow: {run.get('name')}",
        f"Run ID: {run.get('id')}",
        f"Branch: {run.get('head_branch')}",
        f"Commit: {run.get('head_sha')}",
        f"Conclusion: {run.get('conclusion')}",
        f"Generated: {timestamp}",
        "",
        "## CI Evidence",
        "",
        "```text",
        evidence,
        "```",
        "",
        "## Agentic Review",
        "",
        review,
        "",
    ]

    content = "\n".join(content_lines)

    report_path.write_text(
        content,
        encoding="utf-8"
    )

    return report_path


def generate_review(system_prompt, review_prompt, evidence):
    review = generate(
        system_prompt
        + "\n\n"
        + review_prompt
    )

    if not review:
        raise RuntimeError(
            "Qwen returned an empty review."
        )

    if has_required_sections(review):
        return review

    print(
        "[OBSERVE] Qwen response was missing "
        "required sections. Retrying..."
    )

    retry_prompt = f"""
The previous response did not follow the required format.

Return exactly these four sections:

## PLAN
## ACT
## OBSERVE
## ADAPT

Every section must be present.

Do not add any other headings.

Do not omit the ADAPT section.

Use only the CI evidence supplied below.

If the workflow passed successfully:
- state that clearly in OBSERVE
- do not invent problems
- state in ADAPT that no corrective action is required
- recommend the next appropriate validation step

If the workflow failed:
- identify only failures shown in the evidence
- provide corrective actions based only on those failures

CI EVIDENCE:

{evidence}
"""

    review = generate(
        system_prompt
        + "\n\n"
        + retry_prompt
    )

    if not review:
        raise RuntimeError(
            "Qwen returned an empty review on retry."
        )

    if not has_required_sections(review):
        raise RuntimeError(
            "Qwen failed to return all required "
            "PLAN, ACT, OBSERVE, and ADAPT sections."
        )

    return review


def review_run(run):
    print(
        f"[PLAN] Reviewing {run.get('name')} "
        f"(run {run['id']})"
    )

    print(
        "[ACT] Fetching CI evidence..."
    )

    evidence = build_ci_evidence(run)

    system_prompt = load_prompt(
        "system_prompt.txt"
    )

    review_prompt = load_prompt(
        "review_prompt.txt"
    ).replace(
        "{ci_evidence}",
        evidence
    )

    print(
        "[OBSERVE] Sending CI evidence "
        "to Qwen..."
    )

    review = generate_review(
        system_prompt,
        review_prompt,
        evidence
    )

    print(
        "[ADAPT] Saving review record..."
    )

    report = save_report(
        run,
        evidence,
        review
    )

    return report


def review_new_ci_runs():
    reviewed = load_reviewed_runs()

    runs = get_completed_runs(
        limit=5
    )

    if not runs:
        print(
            "[PLAN] No completed CI runs found."
        )
        return []

    if not reviewed:
        runs_to_review = [
            runs[0]
        ]
    else:
        runs_to_review = [
            run
            for run in runs
            if run["id"] not in reviewed
        ]

    if not runs_to_review:
        print(
            "[PLAN] No new CI runs require review."
        )
        return []

    reports = []

    for run in reversed(runs_to_review):
        report = review_run(run)

        reviewed.add(
            run["id"]
        )

        save_reviewed_runs(
            reviewed
        )

        reports.append(
            report
        )

        print(
            f"[ADAPT] Review saved to {report}"
        )

    return reports