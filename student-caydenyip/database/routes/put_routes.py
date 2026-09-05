from flask import Blueprint, request, jsonify

from db_connection import get_db_connection


put_exam_bp = Blueprint(
    "put_exams",
    __name__
)


@put_exam_bp.put("/exams/<int:exam_id>")
def update_exam(exam_id):

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "error": "Exam data required"
        }), 400

    status = data.get("status")

    if not status:

        return jsonify({
            "error": "status is required"
        }), 400

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
        SET status = ?
        WHERE exam_id = ?
          AND is_deleted = 0
        """,
        (
            status,
            exam_id
        )
    )

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Exam updated successfully"
    }), 200
