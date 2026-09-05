from flask import Blueprint, jsonify

from db_connection import get_db_connection


delete_exam_bp = Blueprint(
    "delete_exams",
    __name__
)


@delete_exam_bp.delete("/exams/<int:exam_id>")
def delete_exam(exam_id):

    conn = get_db_connection()

    exam = conn.execute(
        """
        SELECT exam_id
        FROM student_exams
        WHERE exam_id = ?
          AND is_deleted = 0
        """,
        (exam_id,)
    ).fetchone()

    if exam is None:

        conn.close()

        return jsonify({
            "error": "Exam not found"
        }), 404

    conn.execute(
        """
        UPDATE student_exams
        SET is_deleted = 1
        WHERE exam_id = ?
        """,
        (exam_id,)
    )

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Exam deleted successfully"
    }), 200
