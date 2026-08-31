from flask import Blueprint, jsonify, request

from services.user_service import register_user, login_user

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok"
    }), 200

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not name or not email or not password:
        return jsonify({
            "error": "Name, email and password are required"
        }), 400

    result, status_code = register_user(
        name, email, password
    )

    return jsonify(result), status_code

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Request body is required"
        }), 400

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({
            "error": "Email and password are required"
        }), 400

    result, status_code = login_user(
        email,
        password
    )

    return jsonify(result), status_code