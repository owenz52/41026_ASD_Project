import json
from datetime import date
from pathlib import Path

from flask import Blueprint, jsonify, request

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
    agent_steps = []

    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id")

    if not student_id:
        return jsonify({
            "error": "student_id is required"
        }), 400
    # PLAN
    agent_steps.append({
        "stage": "PLAN",
        "detail": (
            "Analyse the student's incomplete assessments and "
            "determine an appropriate priority order."
        )
    })

    # ACT
    status_code, assignments = database_api.get_assignments({
        "order": "asc"
    })

    if status_code != 200:
        return jsonify({
            "error": "Could not retrieve assignments",
            "agent_steps": agent_steps
        }), status_code

    incomplete_assignments = [
        assignment
        for assignment in assignments
        if assignment["status"] != "completed"
    ]

    if not incomplete_assignments:
        agent_steps.append({
            "stage": "ACT",
            "detail": "Retrieved assignments from the database."
        })

        agent_steps.append({
            "stage": "OBSERVE",
            "detail": "No incomplete assessments were found."
        })

        agent_steps.append({
            "stage": "ADAPT",
            "detail": "No AI prioritisation is required."
        })

        return jsonify({
            "message": "There are no incomplete assignments.",
            "agent_steps": agent_steps
        }), 200

    agent_steps.append({
        "stage": "ACT",
        "detail": (
            f"Retrieved {len(incomplete_assignments)} incomplete "
            "assessment(s) from the database."
        )
    })

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

    # Give the model an explicit current date.
    today = date.today().isoformat()

    task_prompt = (
        f"Today's date is {today}.\n\n"
        + task_prompt
    )

    try:
        recommendation = ask_llm(
            system_prompt,
            task_prompt
        )

        # OBSERVE
        response_text = (
            recommendation.strip()
            if isinstance(recommendation, str)
            else ""
        )

        missing_titles = [
            assignment["title"]
            for assignment in incomplete_assignments
            if assignment["title"].lower()
            not in response_text.lower()
        ]

        has_next_action = (
            "NEXT ACTION:" in response_text.upper()
        )

        valid_response = (
            len(response_text) > 20
            and not missing_titles
            and has_next_action
        )

        if valid_response:
            observe_detail = (
                "The AI response included all incomplete assessments "
                "and a NEXT ACTION recommendation."
            )
        else:
            problems = []

            if len(response_text) <= 20:
                problems.append(
                    "the response was missing or too short"
                )

            if missing_titles:
                problems.append(
                    f"the first AI response omitted {len(missing_titles)} assessments(s)"
                )

            if not has_next_action:
                problems.append(
                    "NEXT ACTION was missing"
                )

            observe_detail = (
                "Validation found: "
                + "; ".join(problems)
                + "."
            )

        agent_steps.append({
            "stage": "OBSERVE",
            "detail": observe_detail
        })

        # ADAPT
        if not valid_response:
            retry_prompt = (
                task_prompt
                + "\n\n"
                + "Your previous response failed validation.\n"
                + f"There are exactly "
                + f"{len(incomplete_assignments)} incomplete assessments.\n"
                + "You must include every assessment exactly once.\n"
                + "Return a numbered priority list from highest "
                + "priority to lowest priority.\n"
                + "Do not invent dates or assessments.\n"
                + "Use the supplied current date when discussing urgency.\n"
                + "Finish with exactly one NEXT ACTION identifying "
                + "the single highest priority assessment."
            )

            recommendation = ask_llm(
                system_prompt,
                retry_prompt
            )

            agent_steps.append({
                "stage": "ADAPT",
                "detail": (
                    "The response failed validation, so the AI was "
                    "retried with stricter instructions requiring all "
                    "assessments and one NEXT ACTION."
                )
            })

        else:
            agent_steps.append({
                "stage": "ADAPT",
                "detail": (
                    "The response passed validation, so no retry "
                    "was required."
                )
            })

        return jsonify({
            "recommendation": recommendation,
            "agent_steps": agent_steps
        }), 200

    except Exception as error:
        return jsonify({
            "error": "AI request failed",
            "detail": str(error),
            "agent_steps": agent_steps
        }), 500