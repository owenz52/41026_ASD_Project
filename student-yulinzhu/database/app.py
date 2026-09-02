import os
import sqlite3

from flask import Flask, jsonify, request
app = Flask(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DATABASE_NAME = os.path.join(DATA_DIR, "enrolment.db")

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/courses", methods=["GET"])
def get_courses():
    conn = get_db_connection()
    courses = conn.execute(
        "SELECT * FROM courses"
    ).fetchall()
    conn.close()
    return jsonify([dict(course) for course in courses])

@app.route("/enrolments", methods=["GET"])
def get_enrolments():
    conn = get_db_connection()
    enrolments = conn.execute(
        "SELECT * FROM enrolments"
    ).fetchall()
    conn.close()
    return jsonify([dict(enrolment) for enrolment in enrolments])

@app.route("/courses/<int:course_id>", methods=["GET"])
def get_course(course_id):
    conn = get_db_connection()
    course = conn.execute(
        "SELECT * FROM courses WHERE course_id = ?",
        (course_id,)
    ).fetchone()
    conn.close()
    if course is None:
        return jsonify({"error": "Course not found"}), 404
    return jsonify(dict(course))

@app.route("/enrolments/<int:enrolment_id>", methods=["GET"])
def get_enrolment(enrolment_id):
    conn = get_db_connection()
    enrolment = conn.execute(
        "SELECT * FROM enrolments WHERE enrolment_id = ?",
        (enrolment_id,)
    ).fetchone()
    conn.close()
    if enrolment is None:
        return jsonify({"error": "Enrolment not found"}), 404
    return jsonify(dict(enrolment))

@app.route("/enrolments", methods=["POST"])
def create_enrolment():
    data = request.get_json()

    student_id = data.get("student_id")
    course_id = data.get("course_id")
    enrolment_status = data.get("enrolment_status")
    enrolment_date = data.get("enrolment_date")

    if not student_id or not course_id or not enrolment_status or not enrolment_date:
        return jsonify({"error": "Missing required fields"}), 400

    conn = get_db_connection()
    course = conn.execute(
        "SELECT * FROM courses WHERE course_id = ?",
        (course_id,)
    ).fetchone()

    if course is None:
        conn.close()
        return jsonify({"error": "Course not found"}), 404
    existing_enrolment = conn.execute(
        """
        SELECT * FROM enrolments
        WHERE student_id = ? AND course_id = ?
        """,
        (student_id, course_id)
    ).fetchone()

    if existing_enrolment is not None:
        conn.close()
        return jsonify({
            "error": "You are already enrolled in this course"
        }), 409

    cursor = conn.execute(
        """
        INSERT INTO enrolments (
            student_id,
            course_id,
            enrolment_status,
            enrolment_date
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            student_id,
            course_id,
            enrolment_status,
            enrolment_date
        )
    )
    conn.commit()
    enrolment_id = cursor.lastrowid
    conn.close()
    return jsonify({
        "message": "Enrolment created successfully",
        "enrolment_id": enrolment_id
    }), 201

@app.route("/enrolments/<int:enrolment_id>", methods=["PUT"])
def update_enrolment(enrolment_id):
    data = request.get_json()
    course_id = data.get("course_id")
    enrolment_status = data.get("enrolment_status")
    enrolment_date = data.get("enrolment_date")

    if not course_id or not enrolment_status or not enrolment_date:
        return jsonify({"error": "Missing required fields"}), 400

    conn = get_db_connection()
    enrolment = conn.execute(
        "SELECT * FROM enrolments WHERE enrolment_id = ?",
        (enrolment_id,)
    ).fetchone()

    if enrolment is None:
        conn.close()
        return jsonify({"error": "Enrolment not found"}), 404

    course = conn.execute(
        "SELECT * FROM courses WHERE course_id = ?",
        (course_id,)
    ).fetchone()

    if course is None:
        conn.close()
        return jsonify({"error": "Course not found"}), 404

    conn.execute(
        """
        UPDATE enrolments
        SET course_id = ?, enrolment_status = ?, enrolment_date = ?
        WHERE enrolment_id = ?
        """,
        (course_id, enrolment_status, enrolment_date, enrolment_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Enrolment updated successfully"})

@app.route("/enrolments/<int:enrolment_id>", methods=["DELETE"])
def delete_enrolment(enrolment_id):
    conn = get_db_connection()
    enrolment = conn.execute(
        "SELECT * FROM enrolments WHERE enrolment_id = ?",
        (enrolment_id,)
    ).fetchone()

    if enrolment is None:
        conn.close()
        return jsonify({"error": "Enrolment not found"}), 404

    conn.execute(
        "DELETE FROM enrolments WHERE enrolment_id = ?",
        (enrolment_id,)
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Enrolment deleted successfully"})

@app.route("/courses/by-code/<course_code>", methods=["GET"])
def get_course_by_code(course_code):
    conn = get_db_connection()
    course = conn.execute(
        "SELECT * FROM courses WHERE course_code = ?",
        (course_code,)
    ).fetchone()
    conn.close()

    if course is None:
        return jsonify({"error": "Course not found"}), 404

    return jsonify(dict(course))

@app.route("/courses/search", methods=["GET"])
def search_courses():
    keyword = request.args.get("q", "").strip()
    if not keyword:
        return jsonify({"error": "Search keyword is required"}), 400
    conn = get_db_connection()
    cursor = conn.execute(
        "SELECT * FROM courses WHERE lower(course_name) LIKE ? OR lower(course_code) LIKE ?",
        (f"%{keyword}%", f"%{keyword}%")
    ).fetchall()
    conn.close()

    return jsonify([dict(course) for course in cursor])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)