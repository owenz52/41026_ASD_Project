
import json
import os
import sys
from pathlib import Path


AI_SERVICES_DIR = Path(__file__).resolve().parents[2]

if str(AI_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICES_DIR))

from shared_llm.ollama_client import OllamaClient


BASE_DIR = Path(__file__).resolve().parents[1]
PROMPT_PATH = BASE_DIR / "prompts" / "reviewer_prompt.txt"

OLLAMA_REVIEW_MODEL = os.getenv(
    "OLLAMA_REVIEW_MODEL",
    "llama3.1:8b",
)


def load_prompt():
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def review_workflow(
    user_request,
    planner_result,
    worker_result,
    evidence,
):
    """
    Independently review the Worker's output against
    the Planner's instructions and original evidence.
    """

    if not isinstance(planner_result, dict):
        raise ValueError("Planner result must be a dictionary")

    if not isinstance(worker_result, dict):
        raise ValueError("Worker result must be a dictionary")

    if not isinstance(evidence, (dict, list)):
        raise ValueError("Evidence must be a dictionary or list")

    client = OllamaClient()

    prompt = f"""
{load_prompt()}

Original User Request:
{user_request}

Planner Instructions:
{planner_result.get("plan", "")}

Worker Output:
{worker_result.get("output", "")}

ORIGINAL APPLICATION EVIDENCE:
{json.dumps(evidence, indent=2)}
"""

    response = client.generate(
        prompt=prompt,
        model=OLLAMA_REVIEW_MODEL,
        timeout=180,
    )

    if not response:
        raise RuntimeError("Reviewer Agent returned an empty response")

    return {
        "status": "success",
        "agent": "reviewer_agent",
        "model": OLLAMA_REVIEW_MODEL,
        "review": response,
        "human_approval_required": True,
    }
