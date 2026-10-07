from flask import Blueprint, jsonify, request

from services import deadline_service, mcp_client, mcp_policy, rag_client
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

    # The exam service requires student_id and answers 400 without it, so the
    # probe sends one. Any positive id works; this only checks reachability.
    probe_student = request.args.get("student_id", "1")

    def reachable(url, path="", params=None):
        try:
            response = _requests.get(f"{url}{path}", params=params, timeout=4)
            return {"ok": response.status_code < 400, "status": response.status_code}
        except _requests.RequestException as error:
            return {"ok": False, "error": type(error).__name__}

    return jsonify({
        "mcp": mcp_client.health(),
        "rag": rag_client.health(),
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
                      **reachable(EXAM_SERVICE_URL, "/exams",
                                  {"student_id": probe_student})},
        },
    })


@ai_mode_bp.get("/ai/mcp/tools")
def mcp_tools_route():
    """The shared MCP tools this feature is allowed to use.

    The server registers every feature's tools; the calendar only lists its
    own (see services/mcp_policy.py).
    """
    try:
        result = mcp_policy.filter_tools(mcp_client.list_tools())
        return jsonify(result), 200 if result.get("ok") else 503
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@ai_mode_bp.post("/ai/mcp/invoke")
def mcp_invoke_route():
    """Invoke one allowed shared MCP tool and return its structured result.

    The frontend calls this rather than the MCP server directly, so the
    browser never speaks the MCP protocol itself. Tool boundaries:
      403  the tool is not one of the calendar's
      400  student_id missing, or an argument is unexpected or out of range
    student_id comes from the request body and overrides any value inside
    "arguments".
    """
    data = request.get_json(silent=True) or {}
    tool = data.get("tool")
    student_id = data.get("student_id")

    if not tool:
        return jsonify({"error": "tool is required"}), 400
    if not mcp_policy.is_allowed(tool):
        return jsonify({"ok": False, "tool": tool,
                        "error": f"tool '{tool}' is not available to the calendar"}), 403
    if not student_id:
        return jsonify({"error": "student_id is required"}), 400

    try:
        student_id = int(student_id)
    except (TypeError, ValueError):
        return jsonify({"error": "student_id must be a number"}), 400

    arguments, problem = mcp_policy.validate(tool, data.get("arguments"), student_id)
    if problem:
        return jsonify({"ok": False, "tool": tool, "error": problem}), 400

    try:
        result = mcp_client.invoke(tool, arguments)
        return jsonify(result), 200 if result.get("ok") else 503
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@ai_mode_bp.post("/ai/rag/ask")
def rag_ask_route():
    """Ask the shared RAG server about this student's calendar.

    The shared server is stateless, so the calendar supplies the documents
    to search. Answers always carry citations and a confidence category, and
    an unsupported answer is reported as insufficient context instead.
    """
    data = request.get_json(silent=True) or {}
    question = data.get("question")
    student_id = data.get("student_id")

    if not question:
        return jsonify({"error": "question is required"}), 400
    if not student_id:
        return jsonify({"error": "student_id is required"}), 400

    try:
        result = rag_client.ask_for_student(question, student_id,
                                            data.get("top_k"))
        return jsonify(result), 200 if result.get("ok") else 503
    except Exception as error:
        return jsonify({"error": str(error)}), 500
