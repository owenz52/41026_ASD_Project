
import json
import os
import sys
from pathlib import Path


AI_SERVICES_DIR = Path(__file__).resolve().parents[2]

if str(AI_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICES_DIR))

from shared_llm.ollama_client import OllamaClient  # noqa: E402


BASE_DIR = Path(__file__).resolve().parents[1]
PROMPT_PATH = BASE_DIR / "prompts" / "planner_prompt.txt"

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")


def load_prompt():
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def fallback_plan(user_request):
    """Provide a safe plan if the LLM produces an incomplete response."""
    return (
        f"Objective:\n{user_request}\n\n"
        "Steps:\n"
        "1. Identify what information the request requires.\n"
        "2. Examine the supplied evidence for relevant records.\n"
        "3. Identify missing or incomplete information.\n"
        "4. Pass the task and available evidence to the Worker.\n"
        "5. Submit the completed workflow for review.\n\n"
        "Evidence Required:\n"
        "Records relevant to the user's request, including the "
        "fields needed to support any conclusions.\n\n"
        "Human Approval:\n"
        "A human must review the final result before approval."
    )


def plan_is_complete(plan):
    """Check that all required sections contain meaningful content."""
    headings = (
        "Objective:",
        "Steps:",
        "Evidence Required:",
        "Human Approval:",
    )

    positions = []

    for heading in headings:
        position = plan.find(heading)

        if position == -1:
            return False

        positions.append(position)

    if positions != sorted(positions):
        return False

    for index, heading in enumerate(headings):
        start = positions[index] + len(heading)
        end = (
            positions[index + 1]
            if index + 1 < len(headings)
            else len(plan)
        )

        if not plan[start:end].strip():
            return False

    return True


def plan_workflow(user_request, evidence=None):
    """Generate a structured plan for the requested workflow."""

    if not isinstance(user_request, str) or not user_request.strip():
        raise ValueError("User request must be a non-empty string")

    if evidence is None:
        evidence = {}

    if not isinstance(evidence, (dict, list)):
        raise ValueError("Evidence must be a dictionary or list")

    client = OllamaClient()

    prompt = f"""
{load_prompt()}

User Request:
{user_request}

Available Evidence:
{json.dumps(evidence, indent=2)}

IMPORTANT:
The user request is not evidence of existing records.
If Available Evidence is empty, explain which records
would be required to complete the task.
Do not claim that missing evidence has been supplied.
Every required section must contain meaningful content.
"""

    response = client.generate(
        prompt=prompt,
        model=OLLAMA_MODEL,
        timeout=120,
    )

    if not response or not plan_is_complete(response):
        response = fallback_plan(user_request)

    return {
        "status": "success",
        "agent": "planner_agent",
        "model": OLLAMA_MODEL,
        "objective": user_request,
        "plan": response,
        "human_approval_required": True,
    }


if __name__ == "__main__":
    result = plan_workflow(
        user_request="Identify my most urgent upcoming assessments",
        evidence={
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
        },
    )

    print(json.dumps(result, indent=2))
