import sqlite3
from os import getenv
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, request


app = Flask(__name__)

DATABASE_PATH = Path(__file__).parent / "assessment_tracker.db"


def get_db_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


#Get all assignments
@app.get("/assignments")
def get_assignments():
    student_id = request.args.get("student_id")
    course_id = request.args.get("course_id")
    status = request.args.get("status")
    due = request.args.get("due")
    order = request.args.get("order", "asc").lower()

    if order not in ("asc", "desc"):
        return jsonify({
            "error": "Order must be asc or desc"
        }), 400

    query = """
        SELECT *
        FROM assignments
        WHERE 1 = 1
    """

    parameters = []

    if student_id:
        query += " AND student_id = ?"
        parameters.append(student_id)

    if course_id:
        query += " AND course_id = ?"
        parameters.append(course_id)

    if status:
        query += " AND status = ?"
        parameters.append(status)

    today = date.today().isoformat()

    if due == "upcoming":
        query += """
            AND due_date >= ?
            AND status != 'completed'
        """
        parameters.append(today)

    elif due == "overdue":
        query += """
            AND due_date < ?
            AND status != 'completed'
        """
        parameters.append(today)

    query += f" ORDER BY due_date {order.upper()}"

    connection = get_db_connection()

    try:
        assignments = connection.execute(
            query,
            parameters
        ).fetchall()

        return jsonify([
            dict(assignment)
            for assignment in assignments
        ])

    finally:
        connection.close()


#Get assignment by ID
@app.get("/assignments/<int:assignment_id>")
def get_assignment(assignment_id):
    connection = get_db_connection()

    try:
        assignment = connection.execute(
            """
            SELECT *
            FROM assignments
            WHERE assignment_id = ?
            """,
            (assignment_id,)
        ).fetchone()

        if assignment is None:
            return jsonify({
                "error": "Assignment not found"
            }), 404

        return jsonify(dict(assignment))

    finally:
        connection.close()


#Create assignment
@app.post("/assignments")
def create_assignment():
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    required_fields = [
        "student_id",
        "course_id",
        "title",
        "due_date"
    ]

    for field in required_fields:
        if data.get(field) in (None, ""):
            return jsonify({
                "error": f"{field} is required"
            }), 400

    status = data.get(
        "status",
        "not_started"
    )

    allowed_statuses = [
        "not_started",
        "in_progress",
        "completed"
    ]

    if status not in allowed_statuses:
        return jsonify({
            "error": "Invalid status"
        }), 400

    connection = get_db_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO assignments (
                student_id,
                course_id,
                title,
                description,
                due_date,
                weighting,
                status,
                completion_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["student_id"],
                data["course_id"],
                data["title"],
                data.get("description"),
                data["due_date"],
                data.get("weighting"),
                status,
                data.get("completion_date")
            )
        )

        connection.commit()

        assignment = connection.execute(
            """
            SELECT *
            FROM assignments
            WHERE assignment_id = ?
            """,
            (cursor.lastrowid,)
        ).fetchone()

        return jsonify(
            dict(assignment)
        ), 201

    finally:
        connection.close()


#Update assignment
@app.put("/assignments/<int:assignment_id>")
def update_assignment(assignment_id):
    data = request.get_json() or {}

    connection = get_db_connection()

    try:
        assignment = connection.execute(
            """
            SELECT *
            FROM assignments
            WHERE assignment_id = ?
            """,
            (assignment_id,)
        ).fetchone()

        if assignment is None:
            return jsonify({
                "error": "Assignment not found"
            }), 404

        status = data.get(
            "status",
            assignment["status"]
        )

        if status not in [
            "not_started",
            "in_progress",
            "completed"
        ]:
            return jsonify({
                "error": "Invalid status"
            }), 400

        completion_date = data.get(
            "completion_date",
            assignment["completion_date"]
        )

        if status != "completed":
            completion_date = None

        connection.execute(
            """
            UPDATE assignments
            SET
                student_id = ?,
                course_id = ?,
                title = ?,
                description = ?,
                due_date = ?,
                weighting = ?,
                status = ?,
                completion_date = ?
            WHERE assignment_id = ?
            """,
            (
                data.get(
                    "student_id",
                    assignment["student_id"]
                ),
                data.get(
                    "course_id",
                    assignment["course_id"]
                ),
                data.get(
                    "title",
                    assignment["title"]
                ),
                data.get(
                    "description",
                    assignment["description"]
                ),
                data.get(
                    "due_date",
                    assignment["due_date"]
                ),
                data.get(
                    "weighting",
                    assignment["weighting"]
                ),
                status,
                completion_date,
                assignment_id
            )
        )

        connection.commit()

        updated_assignment = connection.execute(
            """
            SELECT *
            FROM assignments
            WHERE assignment_id = ?
            """,
            (assignment_id,)
        ).fetchone()

        return jsonify(
            dict(updated_assignment)
        )

    finally:
        connection.close()


#Delete assignment
@app.delete("/assignments/<int:assignment_id>")
def delete_assignment(assignment_id):
    connection = get_db_connection()

    try:
        cursor = connection.execute(
            """
            DELETE FROM assignments
            WHERE assignment_id = ?
            """,
            (assignment_id,)
        )

        if cursor.rowcount == 0:
            return jsonify({
                "error": "Assignment not found"
            }), 404

        connection.commit()

        return jsonify({
            "message": "Assignment deleted"
        })

    finally:
        connection.close()


#Update assignment status
@app.patch("/assignments/<int:assignment_id>/status")
def update_assignment_status(assignment_id):
    data = request.get_json() or {}
    status = data.get("status")

    if status not in [
        "not_started",
        "in_progress",
        "completed"
    ]:
        return jsonify({
            "error": "Invalid status"
        }), 400

    connection = get_db_connection()

    try:
        assignment = connection.execute(
            """
            SELECT assignment_id
            FROM assignments
            WHERE assignment_id = ?
            """,
            (assignment_id,)
        ).fetchone()

        if assignment is None:
            return jsonify({
                "error": "Assignment not found"
            }), 404

        if status == "completed":
            connection.execute(
                """
                UPDATE assignments
                SET
                    status = ?,
                    completion_date = CURRENT_TIMESTAMP
                WHERE assignment_id = ?
                """,
                (status, assignment_id)
            )

        else:
            connection.execute(
                """
                UPDATE assignments
                SET
                    status = ?,
                    completion_date = NULL
                WHERE assignment_id = ?
                """,
                (status, assignment_id)
            )

        connection.commit()

        updated_assignment = connection.execute(
            """
            SELECT *
            FROM assignments
            WHERE assignment_id = ?
            """,
            (assignment_id,)
        ).fetchone()

        return jsonify(
            dict(updated_assignment)
        )

    finally:
        connection.close()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(getenv("DATABASE_PORT", 5008)),
        debug=True,
        use_reloader=False
    )