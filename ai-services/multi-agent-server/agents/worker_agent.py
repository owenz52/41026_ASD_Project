
import json
import os
import sys
from datetime import date
from pathlib import Path


AI_SERVICES_DIR = Path(__file__).resolve().parents[2]

if str(AI_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICES_DIR))

from shared_llm.ollama_client import OllamaClient  # noqa: E402


BASE_DIR = Path(__file__).resolve().parents[1]
PROMPT_PATH = BASE_DIR / "prompts" / "worker_prompt.txt"

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")


def load_prompt():
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def get_assignments(evidence):
    """Extract explicitly supplied assignment records."""
    if isinstance(evidence, dict):
        assignments = evidence.get("assignments")
    elif isinstance(evidence, list):
        assignments = evidence
    else:
        return None

    if not isinstance(assignments, list):
        return None

    return assignments


def is_prioritisation_request(user_request):
    """Identify requests requiring chronological assessment ordering."""
    request = user_request.lower()

    keywords = (
        "urgent",
        "priority",
        "prioritise",
        "prioritize",
        "due first",
        "earliest",
        "deadline",
        "chronological",
        "upcoming assessments",
    )

    return any(keyword in request for keyword in keywords)


def prioritise_assignments(assignments):
    """Sort supplied assignments chronologically without using an LLM."""
    valid = []
    missing_dates = []

    for assignment in assignments:
        if not isinstance(assignment, dict):
            missing_dates.append("Invalid assignment record")
            continue

        title = assignment.get("title", "Untitled assignment")
        due_date = assignment.get("due_date")

        try:
            parsed_date = date.fromisoformat(due_date)
        except (TypeError, ValueError):
            missing_dates.append(str(title))
            continue

        valid.append((parsed_date, assignment))

    valid.sort(key=lambda item: item[0])

    if not valid:
        return (
            "Output:\n"
            "Cannot prioritise assessments because no valid "
            "due dates were provided.\n\n"
            "Evidence Used:\n"
            "No valid assessment deadlines.\n\n"
            "Limitations:\n"
            "Valid due dates in YYYY-MM-DD format are required."
        )

    earliest_date = valid[0][0]

    lines = [
        "Output:",
        "Assessment deadline priority (earliest first):",
    ]

    for index, (due_date, assignment) in enumerate(valid, start=1):
        title = assignment.get("title", "Untitled assignment")

        lines.append(
            f"{index}. {title} — {due_date.isoformat()}"
        )

    most_urgent = [
        assignment.get("title", "Untitled assignment")
        for due_date, assignment in valid
        if due_date == earliest_date
    ]

    lines.extend([
        "",
        "Highest deadline priority:",
        ", ".join(most_urgent),
        f"Due on {earliest_date.isoformat()}.",
        "",
        "Evidence Used:",
        "Supplied assignment titles and due_date fields.",
        "",
        "Limitations:",
    ])

    if missing_dates:
        lines.append(
            "Could not rank records with missing or invalid "
            "due dates: " + ", ".join(missing_dates)
        )
    else:
        lines.append(
            "Ranking is based only on supplied due dates; "
            "other workload factors were not provided."
        )

    return "\n".join(lines)


def execute_workflow(user_request, planner_result, evidence):
    """
    Execute a planned task using supplied evidence.
    Does not modify application data.
    """

    if not isinstance(evidence, (dict, list)):
        raise ValueError("Evidence must be a dictionary or list")

    if not isinstance(planner_result, dict):
        raise ValueError("Planner result must be a dictionary")

    plan = planner_result.get("plan", "")

    if not plan:
        raise ValueError("Planner result does not contain a plan")

    assignments = get_assignments(evidence)

    evidence_is_empty = (
        not evidence
        or assignments == []
    )

    if evidence_is_empty:
        return {
            "status": "success",
            "agent": "worker_agent",
            "model": None,
            "output": (
                "Output:\n"
                "Cannot identify or prioritise assessments because "
                "no assessment records were supplied.\n\n"
                "Evidence Used:\n"
                "None supplied.\n\n"
                "Limitations:\n"
                "Assessment records containing titles, due dates "
                "and statuses are required to complete this task."
            ),
            "evidence_count": 0,
            "human_approval_required": True,
        }

    if assignments is not None and is_prioritisation_request(user_request):
        return {
            "status": "success",
            "agent": "worker_agent",
            "model": None,
            "output": prioritise_assignments(assignments),
            "evidence_count": len(assignments),
            "human_approval_required": True,
        }

    client = OllamaClient()

    prompt = f"""
{load_prompt()}

User Request:
{user_request}

Planner Instructions:
{plan}

Application Evidence:
{json.dumps(evidence, indent=2)}

IMPORTANT:
Only Application Evidence contains factual records.
Planner Instructions describe what to do, not what data exists.
Never claim evidence was supplied unless it appears in
Application Evidence.
"""

    response = client.generate(
        prompt=prompt,
        model=OLLAMA_MODEL,
        timeout=120,
    )

    if not response:
        raise RuntimeError("Worker Agent returned an empty response")

    return {
        "status": "success",
        "agent": "worker_agent",
        "model": OLLAMA_MODEL,
        "output": response,
        "evidence_count": (
            len(assignments)
            if assignments is not None
            else len(evidence)
        ),
        "human_approval_required": True,
    }


if __name__ == "__main__":
    from planner_agent import plan_workflow

    evidence = {
        "assignments": [
            {
                "id": 1,
                "title": "Architecture Report",
                "due_date": "2026-10-23",
                "status": "incomplete",
            },
            {
                "id": 2,
                "title": "Cloud Deployment",
                "due_date": "2026-10-28",
                "status": "incomplete",
            },
        ]
    }

    request = "Identify my most urgent upcoming assessments"

    planner_result = plan_workflow(request, evidence)

    worker_result = execute_workflow(
        user_request=request,
        planner_result=planner_result,
        evidence=evidence,
    )

    print(json.dumps({
        "planner": planner_result,
        "worker": worker_result,
    }, indent=2))
