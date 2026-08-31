import os
import sqlite3
from flask import Flask, jsonify, request

app = Flask(__name__)

DATA_DIR = os.getenv("DATA_DIR", "/app/data")
DB_PATH = os.path.join(DATA_DIR, "users.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/users", methods=["GET"])
def get_users():
    conn = get_db()
    users = conn.execute(
        "SELECT user_id, name, email FROM users"
    ).fetchall()
    conn.close()
    return jsonify([dict(user) for user in users])

@app.route("/users", methods=["POST"])
def create_user():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not name or not email or not password:
        return jsonify({
            "error": "Name, email and password are required"
        }), 400
    conn = get_db()

    try:
        cursor = conn.execute(
            """
            INSERT INTO users (name, email, password)
            VALUES (?, ?, ?)
            """,
            (name, email, password)
        )
        conn.commit()
        user_id = cursor.lastrowid

    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "Email already registered"}), 409
    conn.close()

    return jsonify({
        "message": "User creaeted",
        "user_id": user_id
    }), 201

@app.route("/users/email/<email>", methods=["GET"])
def get_user_by_email(email):
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()

    conn.close()

    if user is None:
        return jsonify({"error": "User not found"}), 404
    return jsonify(dict(user))

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5003,
        debug=True
    )