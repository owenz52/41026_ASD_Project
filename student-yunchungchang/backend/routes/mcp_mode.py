import os

from flask import Blueprint, current_app, jsonify, request

from services.mcp_client import search_notes_via_mcp

mcp_mode_bp = Blueprint("mcp_mode", __name__)


@mcp_mode_bp.post("/mcp/notes/search")
def mcp_search_notes():
    enabled = os.getenv("MCP_ENABLED", "true").strip().lower()

    if enabled not in {"true", "1", "yes"}:
        return jsonify({
            "status": "disabled",
            "error": "MCP mode is not enabled",
        }), 503

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required"}), 400

    student_id = data.get("student_id")
    keyword = data.get("keyword")
    limit = data.get("limit", 10)

    if type(student_id) is not int or student_id <= 0:
        return jsonify({"error": "The student_id must be a positive integer"}), 400

    if not isinstance(keyword, str) or not 1 <= len(keyword.strip()) <= 100:
        return jsonify({"error": "The keyword must be a string of 1-100 characters"}), 400

    if type(limit) is not int or not 1 <= limit <= 50:
        return jsonify({"error": "The limit must be an integer between 1 and 50"}), 400

    try:
        result = search_notes_via_mcp(student_id, keyword.strip(), limit)
        return jsonify(result), 200
    except TimeoutError:
        return jsonify({
            "status": "error",
            "error": "MCP request timed out",
        }), 504
    except Exception:
        current_app.logger.exception("Notebook MCP request failed")
        return jsonify({
            "status": "error",
            "error": "Unable to search notes through MCP",
        }), 502
