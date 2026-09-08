from flask import Blueprint, request, jsonify

from db_connection import get_db_connection


reset_exam_bp = Blueprint(
    "reset_exams",
    __name__
)


# ==================================================
# RESET STUDENT EXAMS
# ==================================================

@reset_exam_bp.post("/exams/reset")
def reset_exams():

    student_id = request.args.get(
        "student_id",
        ""
    ).strip()

    data = request.get_json(
        silent=True
    ) or {}

    course_ids = data.get(
        "course_ids",
        []
    )

    # --------------------------------------------------
    # Validate student ID
    # --------------------------------------------------

    if not student_id:

        return jsonify({
            "error": "student_id required"
        }), 400

    # --------------------------------------------------
    # Allow null course_ids
    # --------------------------------------------------

    if course_ids is None:
        course_ids = []

    # --------------------------------------------------
    # course_ids must be a list
    # --------------------------------------------------

    if not isinstance(course_ids, list):

        return jsonify({
            "error": "course_ids must be a list"
        }), 400

    # --------------------------------------------------
    # Ignore null course IDs
    # --------------------------------------------------

    course_ids = [
        course_id
        for course_id in course_ids
        if course_id is not None
    ]

    conn = get_db_connection()

    try:

        # ==================================================
        # 1. DELETE ALL EXISTING EXAMS FOR THIS STUDENT
        # ==================================================

        conn.execute(
            """
            DELETE FROM student_exams
            WHERE student_id = ?
            """,
            (student_id,)
        )

        created = 0

        # ==================================================
        # 2. RE-CREATE EXAMS FROM CURRENT COURSES
        # ==================================================

        for course_id in course_ids:

            course_exams = conn.execute(
                """
                SELECT
                    course_exam_id,
                    course_id,
                    exam_name,
                    exam_date,
                    exam_time
                FROM course_exams
                WHERE course_id = ?
                ORDER BY exam_date, exam_time
                """,
                (course_id,)
            ).fetchall()

            # --------------------------------------------------
            # Add each course exam to student_exams
            # --------------------------------------------------

            for course_exam in course_exams:

                conn.execute(
                    """
                    INSERT INTO student_exams (
                        course_exam_id,
                        course_id,
                        student_id,
                        exam_name,
                        exam_date,
                        exam_time,
                        status,
                        is_deleted
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        course_exam["course_exam_id"],
                        course_exam["course_id"],
                        student_id,
                        course_exam["exam_name"],
                        course_exam["exam_date"],
                        course_exam["exam_time"],
                        "Uncompleted",
                        0
                    )
                )

                created += 1

        # ==================================================
        # 3. COMMIT
        # ==================================================

        conn.commit()

        return jsonify({
            "message": "Exams reset successfully.",
            "student_id": student_id,
            "exams_created": created
        }), 200

    except Exception as exc:

        conn.rollback()

        return jsonify({
            "error": "Failed to reset exams.",
            "details": str(exc)
        }), 500

    finally:

        conn.close()
