
import json
import os
import sys
from pathlib import Path


AI_SERVICES_DIR = Path(__file__).resolve().parents[2]

if str(AI_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICES_DIR))

from shared_llm.ollama_client import OllamaClient


BASE_DIR = Path(__file__).resolve().parents[1]
PROMPT_PATH = BASE_DIR / "prompts" / "worker_prompt.txt"

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")


def load_prompt():
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


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

    client = OllamaClient()

    prompt = f"""
{load_prompt()}

User Request:
{user_request}

Planner Instructions:
{plan}

Application Evidence:
{json.dumps(evidence, indent=2)}
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
            len(evidence.get("assignments", []))
            if isinstance(evidence, dict)
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
