from flask import Blueprint, request, jsonify
import requests

from services.database_api import (
    get_exam_by_id_response,
    get_exams,
    get_exams_by_course_response,
    update_exam_response,
    delete_exam_response,
)


normal_ui_bp = Blueprint("normal_ui", __name__)


@normal_ui_bp.get("/")
def health():
    return jsonify({
        "service": "enrolment-service",
        "status": "running"
    }), 200


@normal_ui_bp.get("/exams")
def get_exams_route():
    try:
        return jsonify(get_exams()), 200

    except requests.RequestException as exc:
        return jsonify({
            "error": "Failed to retrieve exams from database-service.",
            "details": str(exc)
        }), 503


@normal_ui_bp.get("/exams/by-id")
def get_exam_by_id():

    exam_id = request.args.get("exam_id", "").strip()

    if not exam_id:
        return jsonify({
            "error": "Exam ID is required."
        }), 400

    try:

        response = get_exam_by_id_response(exam_id)

        if response.status_code == 404:
            return jsonify({
                "error": "Exam not found."
            }), 404

        if response.status_code == 400:
            return jsonify({
                "error": "Exam ID must be valid."
            }), 400

        response.raise_for_status()

        return jsonify(response.json()), 200

    except requests.RequestException as exc:

        return jsonify({
            "error": "Failed to retrieve exam from database-service.",
            "details": str(exc)
        }), 503


@normal_ui_bp.get("/exams/by-course")
def get_exams_by_course():

    course_id = request.args.get("course_id", "").strip()

    if not course_id:
        return jsonify({
            "error": "Course ID is required."
        }), 400

    try:

        response = get_exams_by_course_response(course_id)

        if response.status_code == 404:
            return jsonify({
                "error": f"No exams found for course {course_id}."
            }), 404

        response.raise_for_status()

        return jsonify(response.json()), 200

    except requests.RequestException as exc:

        return jsonify({
            "error": "Failed to retrieve course exams from database-service.",
            "details": str(exc)
        }), 503


@normal_ui_bp.put("/exams/<int:exam_id>")
def update_exam(exam_id):

    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Exam data is required."
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

        return jsonify(response.json()), response.status_code

    except requests.RequestException as exc:

        return jsonify({
            "error": "Failed to update exam in database-service.",
            "details": str(exc)
        }), 503


@normal_ui_bp.delete("/exams/<int:exam_id>")
def delete_exam(exam_id):

    try:

        response = delete_exam_response(exam_id)

        if response.status_code == 404:
            return jsonify({
                "error": "Exam not found."
            }), 404

        response.raise_for_status()

        return jsonify(response.json()), response.status_code

    except requests.RequestException as exc:

        return jsonify({
            "error": "Failed to delete exam from database-service.",
            "details": str(exc)
        }), 503
