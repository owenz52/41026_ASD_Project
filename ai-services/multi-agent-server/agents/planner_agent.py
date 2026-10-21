
import json
import os
import sys
from pathlib import Path


AI_SERVICES_DIR = Path(__file__).resolve().parents[2]

if str(AI_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICES_DIR))

from shared_llm.ollama_client import OllamaClient


BASE_DIR = Path(__file__).resolve().parents[1]

PROMPT_PATH = BASE_DIR / "prompts" / "planner_prompt.txt"

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")


def load_prompt():
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def plan_workflow(user_request, evidence=None):
    """
    Generate a structured plan for the requested workflow.
    """

    if evidence is None:
        evidence = {}

    client = OllamaClient()

    prompt = f"""
{load_prompt()}

User Request:
{user_request}

Available Evidence:
{json.dumps(evidence, indent=2)}
"""

    response = client.generate(
        prompt=prompt,
        model=OLLAMA_MODEL,
        timeout=120,
    )

    if not response:
        raise RuntimeError("Planner Agent returned an empty response")

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
