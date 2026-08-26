from flask import Blueprint, jsonify, request

from services import database_api


normal_ui_bp = Blueprint("normal_ui", __name__)


@normal_ui_bp.get("/assignments")
def get_assignments():
    params = {
        key: value
        for key, value in request.args.items()
    }

    status_code, data = database_api.get_assignments(params)

    return jsonify(data), status_code


@normal_ui_bp.get("/assignments/<int:assignment_id>")
def get_assignment(assignment_id):
    status_code, data = database_api.get_assignment(assignment_id)

    return jsonify(data), status_code


@normal_ui_bp.post("/assignments")
def create_assignment():
    data = request.get_json() or {}

    status_code, result = database_api.create_assignment(data)

    return jsonify(result), status_code


@normal_ui_bp.put("/assignments/<int:assignment_id>")
def update_assignment(assignment_id):
    data = request.get_json() or {}

    status_code, result = database_api.update_assignment(
        assignment_id,
        data
    )

    return jsonify(result), status_code


@normal_ui_bp.delete("/assignments/<int:assignment_id>")
def delete_assignment(assignment_id):
    status_code, result = database_api.delete_assignment(
        assignment_id
    )

    return jsonify(result), status_code


@normal_ui_bp.patch("/assignments/<int:assignment_id>/status")
def update_assignment_status(assignment_id):
    data = request.get_json() or {}

    status = data.get("status")

    if not status:
        return jsonify({
            "error": "status is required"
        }), 400

    status_code, result = database_api.update_assignment_status(
        assignment_id,
        status
    )

    return jsonify(result), status_code