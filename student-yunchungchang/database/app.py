import sqlite3
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, request


DATABASE_NAME = Path(__file__).resolve().parent / "data" / "notebook.db"

app = Flask(__name__)


def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/notebooks")
def list_notebooks():
    try:
        student_id = request.args.get("student_id")
        course_id = request.args.get("course_id")

        query = "SELECT * FROM notebooks WHERE 1=1"
        params = []
        if student_id is not None:
            query += " AND student_id = ?"
            params.append(student_id)
        if course_id is not None:
            query += " AND course_id = ?"
            params.append(course_id)

        conn = get_db_connection()
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows])
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.get("/notebooks/<int:notebook_id>")
def get_notebook(notebook_id):
    try:
        conn = get_db_connection()
        row = conn.execute(
            "SELECT * FROM notebooks WHERE notebook_id = ?", (notebook_id,)
        ).fetchone()
        conn.close()
        if row is None:
            return jsonify({"error": "notebook not found"}), 404
        return jsonify(dict(row))
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.post("/notebooks")
def create_notebook():
    try:
        data = request.get_json(silent=True) or {}
        for field in ("student_id", "course_id", "notebook_title"):
            if data.get(field) in (None, ""):
                return jsonify({"error": f"{field} is required"}), 400

        created_date = date.today().isoformat()

        conn = get_db_connection()
        cursor = conn.execute(
            "INSERT INTO notebooks (student_id, course_id, notebook_title, created_date) "
            "VALUES (?, ?, ?, ?)",
            (data["student_id"], data["course_id"], data["notebook_title"], created_date),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM notebooks WHERE notebook_id = ?", (cursor.lastrowid,)
        ).fetchone()
        conn.close()
        return jsonify(dict(row)), 201
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.put("/notebooks/<int:notebook_id>")
def update_notebook(notebook_id):
    try:
        conn = get_db_connection()
        existing = conn.execute(
            "SELECT * FROM notebooks WHERE notebook_id = ?", (notebook_id,)
        ).fetchone()
        if existing is None:
            conn.close()
            return jsonify({"error": "notebook not found"}), 404

        data = request.get_json(silent=True) or {}
        updatable = {"student_id", "course_id", "notebook_title"}
        fields = {key: value for key, value in data.items() if key in updatable}

        if fields:
            set_clause = ", ".join(f"{key} = ?" for key in fields)
            conn.execute(
                f"UPDATE notebooks SET {set_clause} WHERE notebook_id = ?",
                (*fields.values(), notebook_id),
            )
            conn.commit()

        row = conn.execute(
            "SELECT * FROM notebooks WHERE notebook_id = ?", (notebook_id,)
        ).fetchone()
        conn.close()
        return jsonify(dict(row))
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.delete("/notebooks/<int:notebook_id>")
def delete_notebook(notebook_id):
    try:
        conn = get_db_connection()
        existing = conn.execute(
            "SELECT * FROM notebooks WHERE notebook_id = ?", (notebook_id,)
        ).fetchone()
        if existing is None:
            conn.close()
            return jsonify({"error": "notebook not found"}), 404

        conn.execute("DELETE FROM notebooks WHERE notebook_id = ?", (notebook_id,))
        conn.commit()
        conn.close()
        return jsonify({"deleted": True, "notebook_id": notebook_id})
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.get("/notebooks/<int:notebook_id>/notes")
def list_notes_for_notebook(notebook_id):
    try:
        conn = get_db_connection()
        notebook = conn.execute(
            "SELECT * FROM notebooks WHERE notebook_id = ?", (notebook_id,)
        ).fetchone()
        if notebook is None:
            conn.close()
            return jsonify({"error": "notebook not found"}), 404

        rows = conn.execute(
            "SELECT * FROM notes WHERE notebook_id = ?", (notebook_id,)
        ).fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows])
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.get("/notes/<int:note_id>")
def get_note(note_id):
    try:
        conn = get_db_connection()
        row = conn.execute(
            "SELECT * FROM notes WHERE note_id = ?", (note_id,)
        ).fetchone()
        conn.close()
        if row is None:
            return jsonify({"error": "note not found"}), 404
        return jsonify(dict(row))
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.post("/notes")
def create_note():
    try:
        data = request.get_json(silent=True) or {}
        for field in ("notebook_id", "note_title", "note_content"):
            if data.get(field) in (None, ""):
                return jsonify({"error": f"{field} is required"}), 400

        conn = get_db_connection()
        notebook = conn.execute(
            "SELECT * FROM notebooks WHERE notebook_id = ?", (data["notebook_id"],)
        ).fetchone()
        if notebook is None:
            conn.close()
            return jsonify({"error": "notebook not found"}), 404

        updated_date = date.today().isoformat()
        cursor = conn.execute(
            "INSERT INTO notes (notebook_id, note_title, note_content, updated_date) "
            "VALUES (?, ?, ?, ?)",
            (data["notebook_id"], data["note_title"], data["note_content"], updated_date),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM notes WHERE note_id = ?", (cursor.lastrowid,)
        ).fetchone()
        conn.close()
        return jsonify(dict(row)), 201
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.put("/notes/<int:note_id>")
def update_note(note_id):
    try:
        conn = get_db_connection()
        existing = conn.execute(
            "SELECT * FROM notes WHERE note_id = ?", (note_id,)
        ).fetchone()
        if existing is None:
            conn.close()
            return jsonify({"error": "note not found"}), 404

        data = request.get_json(silent=True) or {}
        updatable = {"notebook_id", "note_title", "note_content"}
        fields = {key: value for key, value in data.items() if key in updatable}
        fields["updated_date"] = date.today().isoformat()

        set_clause = ", ".join(f"{key} = ?" for key in fields)
        conn.execute(
            f"UPDATE notes SET {set_clause} WHERE note_id = ?",
            (*fields.values(), note_id),
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM notes WHERE note_id = ?", (note_id,)
        ).fetchone()
        conn.close()
        return jsonify(dict(row))
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.delete("/notes/<int:note_id>")
def delete_note(note_id):
    try:
        conn = get_db_connection()
        existing = conn.execute(
            "SELECT * FROM notes WHERE note_id = ?", (note_id,)
        ).fetchone()
        if existing is None:
            conn.close()
            return jsonify({"error": "note not found"}), 404

        conn.execute("DELETE FROM notes WHERE note_id = ?", (note_id,))
        conn.commit()
        conn.close()
        return jsonify({"deleted": True, "note_id": note_id})
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.get("/notes/search")
def search_notes():
    try:
        q = request.args.get("q")
        if not q:
            return jsonify({"error": "q is required"}), 400

        course_id = request.args.get("course_id")

        query = (
            "SELECT notes.*, notebooks.course_id FROM notes "
            "JOIN notebooks ON notes.notebook_id = notebooks.notebook_id "
            "WHERE (lower(notes.note_title) LIKE ? OR lower(notes.note_content) LIKE ?)"
        )
        like_term = f"%{q.lower()}%"
        params = [like_term, like_term]

        if course_id is not None:
            query += " AND notebooks.course_id = ?"
            params.append(course_id)

        conn = get_db_connection()
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows])
    except Exception as error:
        return jsonify({"error": str(error)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004, debug=True)
