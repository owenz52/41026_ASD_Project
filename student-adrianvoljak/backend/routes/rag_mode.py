import logging
from os import getenv

from flask import Blueprint, jsonify, request

from services.rag_client import answer_assessment_question


rag_mode_bp = Blueprint("rag_mode", __name__)
logger = logging.getLogger(__name__)


@rag_mode_bp.post("/rag/assessments/answer")
def assessment_answer():
    if getenv("RAG_ENABLED", "true").lower() != "true":
        return jsonify({
            "status": "disabled",
            "message": "RAG mode is disabled",
        }), 503

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({
            "status": "error",
            "message": "Request body must be a JSON object",
        }), 400

    student_id = data.get("student_id")
    query = data.get("query")

    if type(student_id) is not int or student_id <= 0:
        return jsonify({
            "status": "error",
            "message": "student_id must be a positive integer",
        }), 400

    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 1000:
        return jsonify({
            "status": "error",
            "message": "query must contain between 1 and 1000 characters",
        }), 400

    try:
        result = answer_assessment_question(student_id, query.strip())
        return jsonify(result), 200
    except Exception:
        logger.exception("Assessment RAG request failed")
        return jsonify({
            "status": "error",
            "message": "Unable to answer the question through RAG",
        }), 502