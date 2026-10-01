from flask import Blueprint, request, jsonify
import requests

from services.database_api import (
    get_exam_by_id_response,
    get_exams,
    get_exams_by_course_response,
    sync_exams_response,
    get_student_enrolments,
)


get_exam_bp = Blueprint(
    "get_exams",
    __name__
)


# ==================================================
# GET EXAMS FOR STUDENT
# ==================================================

@get_exam_bp.get("/exams")
def get_exams_route():

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
            "error": "Failed to contact enrolment service.",
            "details": str(exc)
        }), 503

    try:

        # --------------------------------------------------
        # Synchronize the student's exams first.
        #
        # Course-generated exams will have a course_exam_id.
        # Manual exams will have course_exam_id = NULL.
        # --------------------------------------------------

        response = sync_exams_response(
            student_id,
            course_ids
        )

        response.raise_for_status()

        # --------------------------------------------------
        # Retrieve the synchronized exams.
        #
        # The database service now returns:
        #
        # course_exam_id
        # course_id
        # student_id
        # exam_name
        # exam_date
        # exam_time
        # status
        # --------------------------------------------------

        exams = get_exams(
            student_id
        )

        return jsonify(
            exams
        ), 200

    except requests.RequestException as exc:

        return jsonify({
            "error":
                "Failed to synchronize or retrieve exams.",
            "details":
                str(exc)
        }), 503


# ==================================================
# GET EXAM BY ID
# ==================================================

@get_exam_bp.get("/exams/by-id")
def get_exam_by_id():

    exam_id = request.args.get(
        "exam_id",
        ""
    ).strip()

    if not exam_id:

        return jsonify({
            "error": "Exam ID is required."
        }), 400

    # --------------------------------------------------
    # Validate exam ID
    # --------------------------------------------------

    try:

        exam_id = int(exam_id)

    except ValueError:

        return jsonify({
            "error": "Exam ID must be valid."
        }), 400

    try:

        response = get_exam_by_id_response(
            exam_id
        )

        if response.status_code == 404:

            return jsonify({
                "error": "Exam not found."
            }), 404

        response.raise_for_status()

        return jsonify(
            response.json()
        ), 200

    except requests.RequestException as exc:

        return jsonify({
            "error":
                "Failed to retrieve exam from database-service.",
            "details":
                str(exc)
        }), 503


# ==================================================
# GET EXAMS BY COURSE
# ==================================================

@get_exam_bp.get("/exams/by-course")
def get_exams_by_course():

    course_id = request.args.get(
        "course_id",
        ""
    ).strip()

    if not course_id:

        return jsonify({
            "error": "Course ID is required."
        }), 400

    # --------------------------------------------------
    # Validate course ID
    # --------------------------------------------------

    try:

        course_id = int(course_id)

    except ValueError:

        return jsonify({
            "error": "Course ID must be valid."
        }), 400

    try:

        response = get_exams_by_course_response(
            course_id
        )

        if response.status_code == 404:

            return jsonify({
                "error":
                    f"No exams found for course {course_id}."
            }), 404

        response.raise_for_status()

        return jsonify(
            response.json()
        ), 200

    except requests.RequestException as exc:

        return jsonify({
            "error":
                "Failed to retrieve course exams.",
            "details":
                str(exc)
        }), 503
