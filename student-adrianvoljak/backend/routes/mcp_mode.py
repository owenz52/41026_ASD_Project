import logging
from os import getenv

from flask import Blueprint, jsonify, request

from services.mcp_client import get_upcoming_assessments


mcp_mode_bp = Blueprint("mcp_mode", __name__)
logger = logging.getLogger(__name__)


@mcp_mode_bp.get("/mcp/assessments/upcoming")
def upcoming_assessments():
    if getenv("MCP_ENABLED", "true").lower() != "true":
        return jsonify({
            "status": "disabled",
            "message": "MCP mode is disabled",
        }), 503

    try:
        student_id = int(request.args.get("student_id", ""))
        days_ahead = int(request.args.get("days_ahead", "14"))
    except ValueError:
        return jsonify({
            "status": "error",
            "message": "student_id and days_ahead must be integers",
        }), 400

    if student_id <= 0 or not 1 <= days_ahead <= 365:
        return jsonify({
            "status": "error",
            "message": "student_id must be positive; days_ahead must be 1–365",
        }), 400

    try:
        result = get_upcoming_assessments(student_id, days_ahead)
        return jsonify(result), 200
    except Exception:
        logger.exception("Assessment MCP request failed")
        return jsonify({
            "status": "error",
            "message": "Unable to retrieve assessments through MCP",
        }), 502