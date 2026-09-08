from flask import Blueprint, jsonify

from db_connection import get_db_connection


delete_exam_bp = Blueprint(
    "delete_exams",
    __name__
)


# ==================================================
# DELETE EXAM
# ==================================================

@delete_exam_bp.delete("/exams/<int:exam_id>")
def delete_exam(exam_id):

    conn = get_db_connection()

    try:

        exam = conn.execute(
            """
            SELECT
                exam_id,
                course_exam_id
            FROM student_exams
            WHERE exam_id = ?
              AND is_deleted = 0
            """,
            (exam_id,)
        ).fetchone()

        if exam is None:

            return jsonify({
                "error": "Exam not found"
            }), 404

        # --------------------------------------------------
        # Soft delete the exam.
        #
        # course_exam_id is left unchanged so we still
        # know which course exam this student exam came from.
        # --------------------------------------------------

        conn.execute(
            """
            UPDATE student_exams
            SET is_deleted = 1
            WHERE exam_id = ?
            """,
            (exam_id,)
        )

        conn.commit()

        return jsonify({
            "message": "Exam deleted successfully"
        }), 200

    except Exception as exc:

        conn.rollback()

        return jsonify({
            "error": "Failed to delete exam.",
            "details": str(exc)
        }), 500

    finally:

        conn.close()
