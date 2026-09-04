from flask import Flask, jsonify, request
import sqlite3
import os

app = Flask(__name__)

DATABASE_NAME = "/app/data/exam.db"


def get_db_connection():

    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row

    return conn


# ==================================================
# HEALTH CHECK
# ==================================================

@app.get("/")
def health():

    return jsonify({
        "service": "exam-database",
        "status": "running"
    }), 200


# ==================================================
# GET EXAMS FOR STUDENT
# ==================================================

@app.get("/exams")
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

@app.get("/exams/<int:exam_id>")
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

@app.get("/exams/by-course")
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


# ==================================================
# UPDATE EXAM
# ==================================================

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
        FROM student_exams
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
        UPDATE student_exams
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


# ==================================================
# DELETE EXAM
# ==================================================

@app.delete("/exams/<int:exam_id>")
def delete_exam(exam_id):

    conn = get_db_connection()

    exam = conn.execute(
        """
        SELECT exam_id
        FROM student_exams
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
        DELETE FROM student_exams
        WHERE exam_id = ?
        """,
        (exam_id,)
    )

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Exam deleted successfully"
    }), 200


# ==================================================
# RESET STUDENT EXAMS
# ==================================================

@app.post("/exams/reset")
def reset_exams():

    student_id = request.args.get(
        "student_id",
        ""
    ).strip()

    data = request.get_json(silent=True) or {}

    course_ids = data.get("course_ids", [])

    if not student_id:
        return jsonify({
            "error": "student_id required"
        }), 400

    if not course_ids:
        return jsonify({
            "error": "course_ids required"
        }), 400

    conn = get_db_connection()

    try:

        # Delete existing exams
        conn.execute(
            """
            DELETE FROM student_exams
            WHERE student_id = ?
            """,
            (student_id,)
        )

        created = 0

        # Re-create exams for enrolled courses
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
                """,
                (course_id,)
            ).fetchall()

            for course_exam in course_exams:

                conn.execute(
                    """
                    INSERT INTO student_exams (
                        course_id,
                        student_id,
                        exam_name,
                        exam_date,
                        exam_time,
                        status
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        course_exam["course_id"],
                        student_id,
                        course_exam["exam_name"],
                        course_exam["exam_date"],
                        course_exam["exam_time"],
                        "Uncompleted"
                    )
                )

                created += 1

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



@app.post("/exams/sync")
def sync_exams():

    student_id = request.args.get(
        "student_id",
        ""
    ).strip()

    data = request.get_json(silent=True) or {}

    course_ids = data.get("course_ids", [])

    if not student_id:

        return jsonify({
            "error": "student_id required"
        }), 400

    if not isinstance(course_ids, list):

        return jsonify({
            "error": "course_ids must be a list"
        }), 400

    conn = get_db_connection()

    try:

        added = 0
        skipped = 0

        # --------------------------------------------------
        # Check every enrolled course
        # --------------------------------------------------

        for course_id in course_ids:

            # Get all exam templates for this course
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

            for course_exam in course_exams:

                # Check whether this student already has
                # this particular exam
                existing_exam = conn.execute(
                    """
                    SELECT exam_id
                    FROM student_exams
                    WHERE student_id = ?
                      AND course_id = ?
                      AND exam_name = ?
                      AND exam_date = ?
                      AND exam_time = ?
                    """,
                    (
                        student_id,
                        course_exam["course_id"],
                        course_exam["exam_name"],
                        course_exam["exam_date"],
                        course_exam["exam_time"]
                    )
                ).fetchone()

                # Already exists
                if existing_exam:

                    skipped += 1
                    continue

                # Add missing exam
                conn.execute(
                    """
                    INSERT INTO student_exams (
                        course_id,
                        student_id,
                        exam_name,
                        exam_date,
                        exam_time,
                        status
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        course_exam["course_id"],
                        student_id,
                        course_exam["exam_name"],
                        course_exam["exam_date"],
                        course_exam["exam_time"],
                        "Uncompleted"
                    )
                )

                added += 1

        conn.commit()

        return jsonify({
            "message": "Exams synchronized successfully.",
            "student_id": student_id,
            "exams_added": added,
            "exams_already_existing": skipped
        }), 200

    except Exception as exc:

        conn.rollback()

        return jsonify({
            "error": "Failed to synchronize exams.",
            "details": str(exc)
        }), 500

    finally:

        conn.close()


# ==================================================
# ADD EXAM
# ==================================================

@app.post("/exams")
def add_exam():

    data = request.get_json(silent=True) or {}

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
            "error": "student_id required"
        }), 400

    if course_id is None or str(course_id).strip() == "":
        return jsonify({
            "error": "course_id required"
        }), 400

    if exam_name is None or str(exam_name).strip() == "":
        return jsonify({
            "error": "exam_name required"
        }), 400

    if exam_date is None or str(exam_date).strip() == "":
        return jsonify({
            "error": "exam_date required"
        }), 400

    if exam_time is None or str(exam_time).strip() == "":
        return jsonify({
            "error": "exam_time required"
        }), 400

    conn = get_db_connection()

    try:

        # --------------------------------------------------
        # Add the exam
        # --------------------------------------------------

        cursor = conn.execute(
            """
            INSERT INTO student_exams (
                course_id,
                student_id,
                exam_name,
                exam_date,
                exam_time,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                course_id,
                student_id,
                exam_name,
                exam_date,
                exam_time,
                "Uncompleted"
            )
        )

        conn.commit()

        exam_id = cursor.lastrowid

        return jsonify({
            "message": "Exam added successfully.",
            "exam_id": exam_id
        }), 201

    except Exception as exc:

        conn.rollback()

        return jsonify({
            "error": "Failed to add exam.",
            "details": str(exc)
        }), 500

    finally:

        conn.close()




# ==================================================
# START SERVER
# ==================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5010,
        debug=True
    )

    # ==================================================
# SYNC STUDENT EXAMS
# ==================================================

