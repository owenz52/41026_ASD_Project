from flask import Blueprint, jsonify, request

from services.ai_orchestrator import (
    LLMUnavailableError,
    NoteNotFoundError,
    recommend_notes,
    summarise_note,
)

ai_mode_bp = Blueprint("ai_mode", __name__)


@ai_mode_bp.post("/ai/summarise")
def summarise_route():
    data = request.get_json(silent=True) or {}
    note_id = data.get("note_id")
    if not note_id:
        return jsonify({"error": "note_id is required"}), 400
    try:
        return jsonify(summarise_note(note_id))
    except NoteNotFoundError:
        return jsonify({"error": "note not found"}), 404
    except LLMUnavailableError as error:
        return jsonify({"error": "AI service unavailable", "detail": str(error)}), 502
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@ai_mode_bp.post("/ai/recommend")
def recommend_route():
    data = request.get_json(silent=True) or {}
    note_id = data.get("note_id")
    if not note_id:
        return jsonify({"error": "note_id is required"}), 400
    try:
        return jsonify(recommend_notes(note_id))
    except NoteNotFoundError:
        return jsonify({"error": "note not found"}), 404
    except LLMUnavailableError as error:
        return jsonify({"error": "AI service unavailable", "detail": str(error)}), 502
    except Exception as error:
        return jsonify({"error": str(error)}), 500
