import os
import sqlite3
from datetime import datetime, timedelta

from flask import Flask, jsonify, request

app = Flask(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DATABASE_NAME = os.path.join(DATA_DIR, "calendar.db")
DATABASE_PORT = int(os.getenv("DATABASE_PORT", 5006))

TIME_FORMAT = "%Y-%m-%d %H:%M"


def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def parse_time(value):
    """Parse a 'YYYY-MM-DD HH:MM' string, tolerating the ISO 'T' separator."""
    if value is None:
        return None
    return datetime.strptime(value.replace("T", " ")[:16], TIME_FORMAT)


@app.route("/events", methods=["GET"])
def list_events():
    student_id = request.args.get("student_id")
    subject = request.args.get("subject")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    if not student_id:
        return jsonify({"error": "student_id is required"}), 400

    sql = "SELECT * FROM events WHERE student_id = ?"
    params = [student_id]

    if subject:
        sql += " AND subject = ?"
        params.append(subject)
    if start_date:
        sql += " AND start_time >= ?"
        params.append(f"{start_date} 00:00")
    if end_date:
        sql += " AND start_time <= ?"
        params.append(f"{end_date} 23:59")

    sql += " ORDER BY start_time"

    conn = get_db_connection()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.route("/events/<int:event_id>", methods=["GET"])
def get_event(event_id):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM events WHERE event_id = ?", (event_id,)
    ).fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "Event not found"}), 404
    return jsonify(dict(row))


@app.route("/events", methods=["POST"])
def create_event():
    data = request.get_json() or {}

    required = ["student_id", "title", "event_type", "start_time", "end_time"]
    missing = [field for field in required if not data.get(field)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    try:
        start = parse_time(data["start_time"])
        end = parse_time(data["end_time"])
    except ValueError:
        return jsonify({"error": "Times must be formatted YYYY-MM-DD HH:MM"}), 400

    if end < start:
        return jsonify({"error": "end_time cannot be before start_time"}), 400

    conn = get_db_connection()
    cursor = conn.execute(
        """
        INSERT INTO events (
            student_id, subject, title, event_type,
            start_time, end_time, location
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["student_id"],
            data.get("subject"),
            data["title"],
            data["event_type"],
            start.strftime(TIME_FORMAT),
            end.strftime(TIME_FORMAT),
            data.get("location", ""),
        ),
    )
    conn.commit()
    event_id = cursor.lastrowid
    row = conn.execute(
        "SELECT * FROM events WHERE event_id = ?", (event_id,)
    ).fetchone()
    conn.close()

    return jsonify(dict(row)), 201


@app.route("/events/<int:event_id>", methods=["PUT"])
def update_event(event_id):
    data = request.get_json() or {}

    conn = get_db_connection()
    existing = conn.execute(
        "SELECT * FROM events WHERE event_id = ?", (event_id,)
    ).fetchone()

    if existing is None:
        conn.close()
        return jsonify({"error": "Event not found"}), 404

    merged = dict(existing)
    for field in [
        "subject", "title", "event_type",
        "start_time", "end_time", "location",
    ]:
        if field in data:
            merged[field] = data[field]

    try:
        start = parse_time(merged["start_time"])
        end = parse_time(merged["end_time"])
    except ValueError:
        conn.close()
        return jsonify({"error": "Times must be formatted YYYY-MM-DD HH:MM"}), 400

    if end < start:
        conn.close()
        return jsonify({"error": "end_time cannot be before start_time"}), 400

    conn.execute(
        """
        UPDATE events
        SET subject = ?, title = ?, event_type = ?,
            start_time = ?, end_time = ?, location = ?,
            updated_at = datetime('now')
        WHERE event_id = ?
        """,
        (
            merged["subject"],
            merged["title"],
            merged["event_type"],
            start.strftime(TIME_FORMAT),
            end.strftime(TIME_FORMAT),
            merged["location"],
            event_id,
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM events WHERE event_id = ?", (event_id,)
    ).fetchone()
    conn.close()

    return jsonify(dict(row))


@app.route("/events/<int:event_id>/move", methods=["PATCH"])
def move_event(event_id):
    """Shift an event to a new date, preserving time of day and duration.

    Accepts either new_date (YYYY-MM-DD) for a whole-day move, or an explicit
    start_time to reschedule to a precise moment.
    """
    data = request.get_json() or {}
    new_date = data.get("new_date")
    new_start = data.get("start_time")

    if not new_date and not new_start:
        return jsonify({"error": "new_date or start_time is required"}), 400

    conn = get_db_connection()
    existing = conn.execute(
        "SELECT * FROM events WHERE event_id = ?", (event_id,)
    ).fetchone()

    if existing is None:
        conn.close()
        return jsonify({"error": "Event not found"}), 404

    try:
        old_start = parse_time(existing["start_time"])
        old_end = parse_time(existing["end_time"])
        duration = old_end - old_start

        if new_start:
            start = parse_time(new_start)
        else:
            target = datetime.strptime(new_date, "%Y-%m-%d").date()
            start = datetime.combine(target, old_start.time())
    except ValueError:
        conn.close()
        return jsonify({"error": "Invalid date or time format"}), 400

    end = start + duration

    conn.execute(
        """
        UPDATE events
        SET start_time = ?, end_time = ?, updated_at = datetime('now')
        WHERE event_id = ?
        """,
        (start.strftime(TIME_FORMAT), end.strftime(TIME_FORMAT), event_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM events WHERE event_id = ?", (event_id,)
    ).fetchone()
    conn.close()

    return jsonify(dict(row))


@app.route("/events/<int:event_id>", methods=["DELETE"])
def delete_event(event_id):
    conn = get_db_connection()
    existing = conn.execute(
        "SELECT * FROM events WHERE event_id = ?", (event_id,)
    ).fetchone()

    if existing is None:
        conn.close()
        return jsonify({"error": "Event not found"}), 404

    conn.execute("DELETE FROM events WHERE event_id = ?", (event_id,))
    conn.commit()
    conn.close()

    return jsonify({"message": "Event deleted successfully", "event_id": event_id})


@app.route("/events/conflicts", methods=["GET"])
def find_conflicts():
    """Return events for a student that overlap the given window.

    exclude_event_id lets a move check for clashes while ignoring the event
    being moved, which would otherwise always overlap itself.
    """
    student_id = request.args.get("student_id")
    start_time = request.args.get("start_time")
    end_time = request.args.get("end_time")
    exclude_event_id = request.args.get("exclude_event_id")

    if not student_id or not start_time or not end_time:
        return jsonify({"error": "student_id, start_time and end_time are required"}), 400

    sql = """
        SELECT * FROM events
        WHERE student_id = ?
          AND start_time < ?
          AND end_time > ?
    """
    params = [student_id, end_time.replace("T", " ")[:16], start_time.replace("T", " ")[:16]]

    if exclude_event_id:
        sql += " AND event_id != ?"
        params.append(exclude_event_id)

    conn = get_db_connection()
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=DATABASE_PORT, debug=True)
