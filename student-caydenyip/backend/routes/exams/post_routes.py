from flask import Blueprint, request, jsonify
import requests

from services.database_api import (
    add_exam_response,
    reset_exams_response,
    get_student_enrolments,
)


post_exam_bp = Blueprint(
    "post_exams",
    __name__
)


@post_exam_bp.post("/exams")
def add_exam():

    data = request.get_json(
        silent=True
    ) or {}

    student_id = data.get("student_id")
    course_id = data.get("course_id")
    exam_name = data.get("exam_name")
    exam_date = data.get("exam_date")
    exam_time = data.get("exam_time")

    if not student_id:
        return jsonify({
            "error": "Student ID is required."
        }), 400

    if not course_id:
        return jsonify({
            "error": "Course ID is required."
        }), 400

    if not exam_name:
        return jsonify({
            "error": "Exam name is required."
        }), 400

    if not exam_date:
        return jsonify({
            "error": "Exam date is required."
        }), 400

    if not exam_time:
        return jsonify({
            "error": "Exam time is required."
        }), 400

    try:

        response = add_exam_response(
            student_id,
            course_id,
            exam_name,
            exam_date,
            exam_time
        )

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
                "Failed to add exam to database-service.",
            "details":
                str(exc)
        }), 503


@post_exam_bp.post("/exams/reset")
def reset_exams():

    student_id = request.args.get(
        "student_id",
        ""
    ).strip()

    if not student_id:
        return jsonify({
            "error": "Student ID is required."
        }), 400

    try:

        enrolments = get_student_enrolments(
            student_id
        )

        course_ids = [
            enrolment["course_id"]
            for enrolment in enrolments
            if enrolment.get("course_id") is not None
        ]

    except (KeyError, TypeError, AttributeError) as exc:

        return jsonify({
            "error": "Invalid enrolment data.",
            "details": str(exc)
        }), 500

    except requests.RequestException as exc:

        return jsonify({
            "error":
                "Failed to contact enrolment service.",
            "details":
                str(exc)
        }), 503

    try:

        response = reset_exams_response(
            student_id,
            course_ids
        )

        return jsonify(
            response.json()
        ), response.status_code

    except requests.RequestException as exc:

        return jsonify({
            "error":
                "Exam database request failed.",
            "details":
                str(exc)
        }), 503
