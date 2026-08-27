from flask import Flask, jsonify, request
import sqlite3

app = Flask(__name__)

DATABASE_NAME = "/app/data/enrolment.db"


def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/")
def health():
    return jsonify({
        "service": "database-service",
        "status": "running"
    })


@app.get("/exams")
def get_exams():
    conn = get_db_connection()

    exams = conn.execute(
        """
        SELECT exam_id, course_id, student_id, exam_name,
               exam_date, exam_time, status
        FROM exams
        """
    ).fetchall()

    conn.close()

    return jsonify([dict(row) for row in exams])


@app.get("/exams/<int:exam_id>")
def get_exam(exam_id):
    conn = get_db_connection()

    exam = conn.execute(
        """
        SELECT exam_id, course_id, student_id, exam_name,
               exam_date, exam_time, status
        FROM exams
        WHERE exam_id = ?
        """,
        (exam_id,),
    ).fetchone()

    conn.close()

    if exam is None:
        return jsonify({"error": "Exam not found"}), 404

    return jsonify(dict(exam))


@app.get("/exams/by-course")
def get_exams_by_course():
    course_id = request.args.get("course_id", "").strip()

    if not course_id:
        return jsonify({"error": "course_id required"}), 400

    conn = get_db_connection()

    exams = conn.execute(
        """
        SELECT exam_id, course_id, student_id, exam_name,
               exam_date, exam_time, status
        FROM exams
        WHERE course_id = ?
        """,
        (course_id,),
    ).fetchall()

    conn.close()

    if not exams:
        return jsonify({"error": "No exams found"}), 404

    return jsonify([dict(row) for row in exams])


@app.put("/exams/<int:exam_id>")
def update_exam(exam_id):

    data = request.get_json()

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
        FROM exams
        WHERE exam_id = ?
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
        UPDATE exams
        SET status = ?
        WHERE exam_id = ?
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


@app.delete("/exams/<int:exam_id>")
def delete_exam(exam_id):

    conn = get_db_connection()

    exam = conn.execute(
        """
        SELECT exam_id
        FROM exams
        WHERE exam_id = ?
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
        DELETE FROM exams
        WHERE exam_id = ?
        """,
        (exam_id,)
    )

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Exam deleted successfully"
    }), 200


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5002,
        debug=True
    )
