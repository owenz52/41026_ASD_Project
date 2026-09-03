from flask import Blueprint, jsonify, request

from services import deadline_service
from services.schedule_agent import (
    LLMUnavailableError,
    apply_suggestions,
    suggest_schedule,
)

ai_mode_bp = Blueprint("calendar_ai", __name__)


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


@ai_mode_bp.post("/ai/find-deadlines")
def find_deadlines_route():
    """Assessments and exams not yet on the calendar. Writes nothing."""
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id")

    if not student_id:
        return jsonify({"error": "student_id is required"}), 400

    try:
        return jsonify(deadline_service.find_missing_deadlines(
            student_id,
            from_date=data.get("from_date"),
            horizon_days=data.get("horizon_days", 60),
        ))
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@ai_mode_bp.post("/ai/import-deadlines")
def import_deadlines_route():
    """Create calendar events from deadlines the student accepted."""
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id")
    items = data.get("items")

    if not student_id:
        return jsonify({"error": "student_id is required"}), 400
    if not items:
        return jsonify({"error": "items are required"}), 400

    try:
        return jsonify(deadline_service.import_deadlines(student_id, items))
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@ai_mode_bp.post("/ai/briefing")
def briefing_route():
    """A short summary of today, what is due soon, and the next exam."""
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id")

    if not student_id:
        return jsonify({"error": "student_id is required"}), 400

    try:
        return jsonify(deadline_service.daily_briefing(
            student_id, from_date=data.get("from_date")
        ))
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@ai_mode_bp.get("/ai/diagnostics")
def diagnostics_route():
    """Report what the AI features can and cannot reach.

    Exists because the failure modes look identical from the UI: a missing
    prompt file, an unreachable Ollama and a down source service all end up
    as "the AI was unavailable". This says which one it actually is.
    """
    import requests as _requests

    from config import (
        ASSESSMENT_SERVICE_URL, EXAM_SERVICE_URL,
        OLLAMA_BASE_URL, OLLAMA_MODEL,
    )
    from services.prompt_loader import PROMPT_DIR

    prompts = {}
    for name in ["system_prompt.txt", "context_prompt.txt",
                 "suggest_task_prompt.txt", "suggest_retry_prompt.txt",
                 "briefing_task_prompt.txt"]:
        prompts[name] = (PROMPT_DIR / "service" / "implementation" / name).is_file()

    def reachable(url, path=""):
        try:
            response = _requests.get(f"{url}{path}", timeout=4)
            return {"ok": response.status_code < 400, "status": response.status_code}
        except _requests.RequestException as error:
            return {"ok": False, "error": type(error).__name__}

    return jsonify({
        "prompts": {
            "directory": str(PROMPT_DIR),
            "directory_exists": PROMPT_DIR.is_dir(),
            "files": prompts,
            "all_present": all(prompts.values()),
        },
        "ollama": {
            "url": OLLAMA_BASE_URL,
            "model": OLLAMA_MODEL,
            **reachable(OLLAMA_BASE_URL, "/api/tags"),
        },
        "sources": {
            "assessments": {"url": ASSESSMENT_SERVICE_URL,
                            **reachable(ASSESSMENT_SERVICE_URL, "/assignments")},
            "exams": {"url": EXAM_SERVICE_URL,
                      **reachable(EXAM_SERVICE_URL, "/exams")},
        },
    })
