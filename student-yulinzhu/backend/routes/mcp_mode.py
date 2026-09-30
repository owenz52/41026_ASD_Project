import os
from flask import Blueprint, jsonify, request, current_app
from services.mcp_client import get_courses_via_mcp

mcp_mode_bp = Blueprint("mcp_mode", __name__)

@mcp_mode_bp.post("/mcp/courses")
def mcp_courses():
    enabled = os.getenv("MCP_ENABLED", "true").strip().lower()

    if enabled not in {"true", "1", "yes"}:
        return jsonify({
            "status": "disabled",
            "error": "MCP mode is not enabled",
        }), 503

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "A JSON object is required"
        }), 400

    available_only = data.get("available_only", True)
    if not isinstance(available_only, bool):
        return jsonify({
            "error": "The available_only must be a boolean"
        }), 400

    try:
        result = get_courses_via_mcp(available_only)
        return jsonify(result), 200
    except TimeoutError:
        return jsonify({
            "status": "error",
            "error": "MCP request timed out",
        }), 504
    except Exception:
        current_app.logger.exception("Enrolment MCP request failed")
        return jsonify({
            "status": "error",
            "error": "Unable to retrieve courses through MCP",
        }), 502