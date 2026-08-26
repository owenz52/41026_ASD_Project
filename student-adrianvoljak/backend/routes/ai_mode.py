import json
from pathlib import Path

from flask import Blueprint, jsonify

from services import database_api
from services.llm_client import ask_llm


ai_mode_bp = Blueprint("ai_mode", __name__)

PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"


def load_prompt(filename):
    prompt_path = PROMPT_DIR / filename
    return prompt_path.read_text(
        encoding="utf-8"
    ).strip()


@ai_mode_bp.post("/ai/prioritise")
def prioritise_assignments():
    status_code, assignments = database_api.get_assignments({
        "order": "asc"
    })

    if status_code != 200:
        return jsonify({
            "error": "Could not retrieve assignments"
        }), status_code

    incomplete_assignments = [
        assignment
        for assignment in assignments
        if assignment["status"] != "completed"
    ]

    if not incomplete_assignments:
        return jsonify({
            "message": "There are no incomplete assignments."
        }), 200

    system_prompt = load_prompt(
        "priority_system_prompt.txt"
    )

    task_prompt = load_prompt(
        "priority_task_prompt.txt"
    )

    task_prompt = task_prompt.replace(
        "{{ASSIGNMENTS}}",
        json.dumps(
            incomplete_assignments,
            indent=2
        )
    )

    try:
        recommendation = ask_llm(
            system_prompt,
            task_prompt
        )

        return jsonify({
            "recommendation": recommendation
        }), 200

    except Exception as error:
        return jsonify({
            "error": "AI request failed",
            "detail": str(error)
        }), 500