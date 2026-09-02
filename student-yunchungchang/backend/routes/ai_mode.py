import json

from flask import Blueprint, jsonify, request

from services.database_api import get_note, list_notes
from services.llm_client import ask_llm
from services.prompt_loader import load_prompt

ai_mode_bp = Blueprint("ai_mode", __name__)


@ai_mode_bp.post("/ai/summarise")
def summarise_note():
    data = request.get_json()

    if not data or not data.get("note_id"):
        return jsonify({"error": "note_id is required"}), 400

    note_id = data.get("note_id")

    try:
        status_code, note = get_note(note_id)

        if status_code != 200:
            return jsonify({"error": "Could not retrieve note"}), status_code

        system_prompt = load_prompt("service/implementation/system_prompt.txt")
        context_prompt = load_prompt("service/implementation/context_prompt.txt")

        task_prompt = load_prompt("service/implementation/summarise_task_prompt.txt")
        task_prompt = task_prompt.replace("{{NOTE_TITLE}}", note["note_title"])
        task_prompt = task_prompt.replace("{{NOTE_CONTENT}}", note["note_content"])

        user_prompt = f"{task_prompt}\n\n{context_prompt}"
        summary = ask_llm(system_prompt, user_prompt)

        return jsonify({"summary": summary})
    except Exception as error:
        return jsonify({"error": str(error)}), 500


def check_recommendations(text, candidates):
    """Observe: split the model's reply into lines and check each line against
    the candidate titles it was actually given."""
    lookup = {
        candidate["note_title"].lower(): candidate["note_title"]
        for candidate in candidates
    }

    valid = []
    invented = []

    for line in (text or "").splitlines():
        line = line.strip().lstrip("-*0123456789.) ").rstrip(". ")

        if not line:
            continue

        if line.lower() in lookup:
            title = lookup[line.lower()]
            if title not in valid:
                valid.append(title)
        else:
            invented.append(line)

    return valid, invented


@ai_mode_bp.post("/ai/recommend")
def recommend_notes():
    agent_steps = []

    data = request.get_json()

    if not data or not data.get("note_id"):
        return jsonify({"error": "note_id is required"}), 400

    note_id = data.get("note_id")

    try:
        status_code, note = get_note(note_id)

        if status_code != 200:
            return jsonify({"error": "Could not retrieve note"}), status_code

        # PLAN
        agent_steps.append({
            "stage": "PLAN",
            "detail": (
                f"Find notes related to '{note['note_title']}' from the same "
                "notebook, choosing only from notes that already exist."
            ),
        })

        status_code, notes = list_notes(note["notebook_id"])

        if status_code != 200:
            return jsonify({"error": "Could not retrieve notes"}), status_code

        candidates = [
            candidate
            for candidate in notes
            if candidate["note_id"] != note["note_id"]
        ]

        if not candidates:
            agent_steps.append({
                "stage": "ACT",
                "detail": (
                    "This notebook has no other notes, so the language model "
                    "was not called."
                ),
            })
            agent_steps.append({
                "stage": "OBSERVE",
                "detail": "There were no candidate notes to recommend from.",
            })
            agent_steps.append({
                "stage": "ADAPT",
                "detail": "No AI recommendation is required.",
            })

            return jsonify({
                "recommendations": "There are no other notes in this notebook.",
                "agent_steps": agent_steps,
            })

        candidates_json = json.dumps(candidates, indent=2)

        system_prompt = load_prompt("service/implementation/system_prompt.txt")
        context_prompt = load_prompt("service/implementation/context_prompt.txt")

        task_prompt = load_prompt("service/implementation/recommend_task_prompt.txt")
        task_prompt = task_prompt.replace("{{SOURCE_TITLE}}", note["note_title"])
        task_prompt = task_prompt.replace("{{SOURCE_CONTENT}}", note["note_content"])
        task_prompt = task_prompt.replace("{{CANDIDATES}}", candidates_json)

        # ACT
        user_prompt = f"{task_prompt}\n\n{context_prompt}"
        recommendations = ask_llm(system_prompt, user_prompt)

        agent_steps.append({
            "stage": "ACT",
            "detail": (
                f"Sent {len(candidates)} candidate note(s) from this notebook "
                "to the language model."
            ),
        })

        # OBSERVE
        valid, invented = check_recommendations(recommendations, candidates)

        if invented:
            observe_detail = (
                f"The model returned {len(invented)} title(s) that were not in "
                "the candidate list."
            )
        elif not valid:
            observe_detail = "The model did not return any candidate title."
        else:
            observe_detail = (
                f"All {len(valid)} returned title(s) were in the candidate list."
            )

        agent_steps.append({
            "stage": "OBSERVE",
            "detail": observe_detail,
        })

        # ADAPT
        if invented or not valid:
            titles = "\n".join(candidate["note_title"] for candidate in candidates)
            retry_prompt = (
                f"{user_prompt}\n\n"
                "Your previous response was not accepted.\n"
                "You must choose only from these exact titles:\n"
                f"{titles}\n"
                "Respond with one title per line and nothing else."
            )

            recommendations = ask_llm(system_prompt, retry_prompt)
            valid, invented = check_recommendations(recommendations, candidates)

            adapt_detail = (
                "The response failed validation, so the model was retried with "
                "the exact candidate titles."
            )
        else:
            adapt_detail = (
                "The response passed validation, so no retry was required."
            )

        agent_steps.append({
            "stage": "ADAPT",
            "detail": adapt_detail,
        })

        if valid:
            recommendations = "\n".join(valid)

        return jsonify({
            "recommendations": recommendations,
            "agent_steps": agent_steps,
        })
    except Exception as error:
        return jsonify({"error": str(error)}), 500
