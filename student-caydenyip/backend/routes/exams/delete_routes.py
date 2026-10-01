from flask import Blueprint, jsonify
import requests

from services.database_api import (
    delete_exam_response,
)


delete_exam_bp = Blueprint(
    "delete_exams",
    __name__
)


# ==================================================
# DELETE EXAM
# ==================================================

@delete_exam_bp.delete("/exams/<int:exam_id>")
def delete_exam(exam_id):

    try:

        response = delete_exam_response(
            exam_id
        )

        if response.status_code == 404:

            return jsonify({
                "error": "Exam not found."
            }), 404

        response.raise_for_status()

        return jsonify(
            response.json()
        ), response.status_code

    except requests.RequestException as exc:

        return jsonify({
            "error": "Failed to delete exam.",
            "details": str(exc)
        }), 503
