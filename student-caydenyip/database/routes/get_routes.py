from flask import Blueprint, request, jsonify

from db_connection import get_db_connection


get_exam_bp = Blueprint(
    "get_exams",
    __name__
)


# ==================================================
# GET EXAMS FOR STUDENT
# ==================================================

@get_exam_bp.get("/exams")
def get_exams():

    student_id = request.args.get(
        "student_id",
        ""
    ).strip()

    if not student_id:

        return jsonify({
            "error": "student_id required"
        }), 400

    conn = get_db_connection()

    exams = conn.execute(
        """
        SELECT
            exam_id,
            course_id,
            student_id,
            exam_name,
            exam_date,
            exam_time,
            status
        FROM student_exams
        WHERE student_id = ?
          AND is_deleted = 0
        ORDER BY exam_date, exam_time
        """,
        (student_id,)
    ).fetchall()

    conn.close()

    return jsonify(
        [dict(row) for row in exams]
    ), 200


# ==================================================
# GET EXAM BY ID
# ==================================================

@get_exam_bp.get("/exams/<int:exam_id>")
def get_exam(exam_id):

    conn = get_db_connection()

    exam = conn.execute(
        """
        SELECT
            exam_id,
            course_id,
            student_id,
            exam_name,
            exam_date,
            exam_time,
            status
        FROM student_exams
        WHERE exam_id = ?
          AND is_deleted = 0
        """,
        (exam_id,)
    ).fetchone()

    conn.close()

    if exam is None:

        return jsonify({
            "error": "Exam not found"
        }), 404

    return jsonify(
        dict(exam)
    ), 200


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
            "error": "course_id required"
        }), 400

    conn = get_db_connection()

    exams = conn.execute(
        """
        SELECT
            exam_id,
            course_id,
            student_id,
            exam_name,
            exam_date,
            exam_time,
            status
        FROM student_exams
        WHERE course_id = ?
          AND is_deleted = 0
        ORDER BY exam_date, exam_time
        """,
        (course_id,)
    ).fetchall()

    conn.close()

    if not exams:

        return jsonify({
            "error": "No exams found"
        }), 404

    return jsonify(
        [dict(row) for row in exams]
    ), 200
