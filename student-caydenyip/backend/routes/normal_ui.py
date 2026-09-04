from flask import Blueprint, request, jsonify
import requests

from services.database_api import (
    get_exam_by_id_response,
    get_exams,
    get_exams_by_course_response,
    update_exam_response,
    delete_exam_response,
    reset_exams_response,
    sync_exams_response,
    get_student_enrolments,
    add_exam_response,
)



normal_ui_bp = Blueprint("normal_ui", __name__)


@normal_ui_bp.get("/")
def health():

    return jsonify({
        "service": "exam-backend",
        "status": "running"
    }), 200


# ==================================================
# GET EXAMS FOR STUDENT
# ==================================================

@normal_ui_bp.get("/exams")
def get_exams_route():

    student_id = request.args.get(
        "student_id",
        ""
    ).strip()

    if not student_id:
        return jsonify({
            "error": "Student ID is required."
        }), 400

    # ==================================================
    # 1. Get student's current enrolments
    # ==================================================

    try:

        enrolments = get_student_enrolments(
            student_id
        )

    except requests.RequestException as exc:

        return jsonify({
            "error": "Failed to contact enrolment service.",
            "details": str(exc)
        }), 503

    # ==================================================
    # 2. Extract course IDs
    # ==================================================

    try:

        course_ids = [
            enrolment["course_id"]
            for enrolment in enrolments
        ]

    except (KeyError, TypeError) as exc:

        return jsonify({
            "error": "Invalid enrolment data.",
            "details": str(exc)
        }), 500

    # ==================================================
    # 3. Synchronize exams
    # ==================================================

    try:

        sync_response = sync_exams_response(
            student_id,
            course_ids
        )

        sync_response.raise_for_status()

    except requests.RequestException as exc:

        return jsonify({
            "error": "Failed to synchronize exams.",
            "details": str(exc)
        }), 503

    # ==================================================
    # 4. Get the now-synchronized exams
    # ==================================================

    try:

        exams = get_exams(
            student_id
        )

        return jsonify(
            exams
        ), 200

    except requests.RequestException as exc:

        return jsonify({
            "error": "Failed to retrieve exams from database-service.",
            "details": str(exc)
        }), 503


# ==================================================
# GET EXAM BY ID
# ==================================================

@normal_ui_bp.get("/exams/by-id")
def get_exam_by_id():

    exam_id = request.args.get(
        "exam_id",
        ""
    ).strip()


    if not exam_id:

        return jsonify({
            "error": "Exam ID is required."
        }), 400


    try:

        response = get_exam_by_id_response(
                exam_id
            )


        if response.status_code == 404:

            return jsonify({
                "error": "Exam not found."
            }), 404


        if response.status_code == 400:

            return jsonify({
                "error": "Exam ID must be valid."
            }), 400


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

@normal_ui_bp.get("/exams/by-course")
def get_exams_by_course():

    course_id = request.args.get(
        "course_id",
        ""
    ).strip()


    if not course_id:

        return jsonify({
            "error": "Course ID is required."
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
                "Failed to retrieve course exams from database-service.",

            "details":
                str(exc)

        }), 503


# ==================================================
# UPDATE EXAM
# ==================================================

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


        return jsonify(
            response.json()
        ), response.status_code


    except requests.RequestException as exc:

        return jsonify({

            "error":
                "Failed to update exam in database-service.",

            "details":
                str(exc)

        }), 503


# ==================================================
# DELETE EXAM
# ==================================================

@normal_ui_bp.delete("/exams/<int:exam_id>")
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

            "error":
                "Failed to delete exam from database-service.",

            "details":
                str(exc)

        }), 503


# ==================================================
# RESET EXAMS FOR STUDENT
# ==================================================

@normal_ui_bp.post("/exams/reset")
def reset_exams():

    student_id = request.args.get("student_id", "").strip()

    if not student_id:
        return jsonify({
            "error": "Student ID is required."
        }), 400

    try:
        # 1. Get student's enrolments
        enrolments = get_student_enrolments(student_id)

        print("ENROLMENTS:", enrolments)

    except requests.RequestException as exc:
        return jsonify({
            "error": "Failed to contact enrolment service.",
            "details": str(exc)
        }), 503


    try:
        # 2. Get course IDs
        course_ids = [
            enrolment["course_id"]
            for enrolment in enrolments
        ]

        print("COURSE IDS:", course_ids)

    except (KeyError, TypeError) as exc:
        return jsonify({
            "error": "Invalid enrolment data.",
            "details": str(exc)
        }), 500


    try:

        response = reset_exams_response(
        student_id,
        course_ids
    )

        print("STATUS:", response.status_code)
        print("BODY:", response.text)

        return jsonify(response.json()), response.status_code

    except requests.RequestException as exc:

        print("REQUEST ERROR:", repr(exc))

    return jsonify({
        "error": "Exam database request failed.",
        "details": str(exc)
    }), 503


# ==================================================
# ADD EXAM
# ==================================================

@normal_ui_bp.post("/exams")
def add_exam():

    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Exam data is required."
        }), 400

    # Student ID is supplied automatically by the frontend
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
            "error": "Failed to add exam to database-service.",
            "details": str(exc)
        }), 503

