from flask import Blueprint, jsonify, request

from services.schedule_agent import (
    LLMUnavailableError,
    apply_suggestions,
    suggest_schedule,
)

ai_mode_bp = Blueprint("calendar_ai", __name__, url_prefix="/calendar")


@ai_mode_bp.post("/ai/suggest-schedule")
def suggest_schedule_route():
    """Suggest study sessions for upcoming deadlines. Writes nothing."""
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id")

    if not student_id:
        return jsonify({"error": "student_id is required"}), 400

    try:
        return jsonify(suggest_schedule(
            student_id,
            from_date=data.get("from_date"),
            horizon_days=data.get("horizon_days"),
        ))
    except LLMUnavailableError as error:
        return jsonify({"error": "AI service unavailable", "detail": str(error)}), 502
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@ai_mode_bp.post("/ai/apply-suggestions")
def apply_suggestions_route():
    """Create events from suggestions the student has accepted."""
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id")
    suggestions = data.get("suggestions")

    if not student_id:
        return jsonify({"error": "student_id is required"}), 400
    if not suggestions:
        return jsonify({"error": "suggestions are required"}), 400

    try:
        return jsonify(apply_suggestions(student_id, suggestions))
    except Exception as error:
        return jsonify({"error": str(error)}), 500
