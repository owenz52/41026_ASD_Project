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


# ==================================================
# ADD MANUAL EXAM
# ==================================================

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

    # --------------------------------------------------
    # Validate required fields
    # --------------------------------------------------

    if student_id is None or str(student_id).strip() == "":
        return jsonify({
            "error": "Student ID is required."
        }), 400

    if course_id is None or str(course_id).strip() == "":
        return jsonify({
            "error": "Course ID is required."
        }), 400

    if exam_name is None or str(exam_name).strip() == "":
        return jsonify({
            "error": "Exam name is required."
        }), 400

    if exam_date is None or str(exam_date).strip() == "":
        return jsonify({
            "error": "Exam date is required."
        }), 400

    if exam_time is None or str(exam_time).strip() == "":
        return jsonify({
            "error": "Exam time is required."
        }), 400

    try:

        # --------------------------------------------------
        # Manual exams do not have a course_exam_id.
        #
        # The database service will store:
        #
        # course_exam_id = NULL
        # --------------------------------------------------

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


# ==================================================
# RESET STUDENT EXAMS
# ==================================================

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

    # --------------------------------------------------
    # Get student's current enrolments
    # --------------------------------------------------

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

    # --------------------------------------------------
    # Reset exams using the student's current courses.
    #
    # The database service will populate course_exam_id
    # for every course-generated exam.
    # --------------------------------------------------

    try:

        response = reset_exams_response(
            student_id,
            course_ids
        )

        if response.status_code == 400:

            return jsonify({
                "error": "Invalid exam reset data."
            }), 400

        response.raise_for_status()

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
