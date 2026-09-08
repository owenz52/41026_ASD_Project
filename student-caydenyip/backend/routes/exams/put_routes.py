from flask import Blueprint, request, jsonify
import requests

from services.database_api import (
    update_exam_response,
)


put_exam_bp = Blueprint(
    "put_exams",
    __name__
)


# ==================================================
# UPDATE EXAM
# ==================================================

@put_exam_bp.put("/exams/<int:exam_id>")
def update_exam(exam_id):

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "error": "Exam data is required."
        }), 400

    # --------------------------------------------------
    # Only status is updated.
    #
    # course_exam_id is intentionally left unchanged.
    # --------------------------------------------------

    if "status" not in data:

        return jsonify({
            "error": "Status is required."
        }), 400

    if data.get("status") is None or str(
        data.get("status")
    ).strip() == "":

        return jsonify({
            "error": "Status is required."
        }), 400

    try:

        response = update_exam_response(
            exam_id,
            data
        )

        if response.status_code == 404:

            return jsonify({
                "error": "Exam not found."
            }), 404

        if response.status_code == 400:

            return jsonify({
                "error": "Invalid exam data."
            }), 400

        response.raise_for_status()

        return jsonify(
            response.json()
        ), response.status_code

    except requests.RequestException as exc:

        return jsonify({
            "error":
                "Failed to update exam.",
            "details":
                str(exc)
        }), 503
