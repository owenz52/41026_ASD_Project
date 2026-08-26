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


@ai_mode_bp.post("/ai/recommend")
def recommend_notes():
    data = request.get_json()

    if not data or not data.get("note_id"):
        return jsonify({"error": "note_id is required"}), 400

    note_id = data.get("note_id")

    try:
        status_code, note = get_note(note_id)

        if status_code != 200:
            return jsonify({"error": "Could not retrieve note"}), status_code

        status_code, notes = list_notes(note["notebook_id"])

        if status_code != 200:
            return jsonify({"error": "Could not retrieve notes"}), status_code

        candidates = [
            candidate
            for candidate in notes
            if candidate["note_id"] != note["note_id"]
        ]

        if not candidates:
            return jsonify({
                "recommendations": "There are no other notes in this notebook."
            })

        candidates_json = json.dumps(candidates, indent=2)

        system_prompt = load_prompt("service/implementation/system_prompt.txt")
        context_prompt = load_prompt("service/implementation/context_prompt.txt")

        task_prompt = load_prompt("service/implementation/recommend_task_prompt.txt")
        task_prompt = task_prompt.replace("{{SOURCE_TITLE}}", note["note_title"])
        task_prompt = task_prompt.replace("{{SOURCE_CONTENT}}", note["note_content"])
        task_prompt = task_prompt.replace("{{CANDIDATES}}", candidates_json)

        user_prompt = f"{task_prompt}\n\n{context_prompt}"
        recommendations = ask_llm(system_prompt, user_prompt)

        return jsonify({"recommendations": recommendations})
    except Exception as error:
        return jsonify({"error": str(error)}), 500
