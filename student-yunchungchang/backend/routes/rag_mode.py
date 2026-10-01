import os

import requests
from flask import Blueprint, current_app, jsonify, request

from services.rag_client import answer_note_question

rag_mode_bp = Blueprint("rag_mode", __name__)


@rag_mode_bp.post("/rag/notes/answer")
def rag_answer_notes():
    enabled = os.getenv("RAG_ENABLED", "true").strip().lower()

    if enabled not in {"true", "1", "yes"}:
        return jsonify({
            "status": "disabled",
            "error": "RAG mode is not enabled",
        }), 503

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required"}), 400

    student_id = data.get("student_id")
    query = data.get("query")

    if type(student_id) is not int or student_id <= 0:
        return jsonify({"error": "The student_id must be a positive integer"}), 400

    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 1000:
        return jsonify({"error": "The query must be a non-empty string of 1-1000 characters"}), 400

    try:
        result = answer_note_question(student_id, query.strip())
        return jsonify(result), 200
    except requests.Timeout:
        return jsonify({
            "status": "error",
            "error": "RAG request timed out",
        }), 504
    except Exception:
        current_app.logger.exception("Notebook RAG request failed")
        return jsonify({
            "status": "error",
            "error": "Unable to answer the question through RAG",
        }), 502
