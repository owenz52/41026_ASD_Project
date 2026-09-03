from flask import Blueprint, jsonify, request

from services import calendar_service

calendar_bp = Blueprint("calendar", __name__)


@calendar_bp.get("/events")
def list_events():
    try:
        student_id = request.args.get("student_id")
        if not student_id:
            return jsonify({"error": "student_id is required"}), 400

        status_code, body = calendar_service.list_events(
            student_id,
            request.args.get("subject"),
            request.args.get("start_date"),
            request.args.get("end_date"),
        )
        return jsonify(body), status_code
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@calendar_bp.get("/events/<int:event_id>")
def get_event(event_id):
    try:
        status_code, body = calendar_service.get_event(event_id)
        return jsonify(body), status_code
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@calendar_bp.post("/events")
def add_event():
    try:
        status_code, body = calendar_service.add_event(request.get_json() or {})
        return jsonify(body), status_code
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@calendar_bp.put("/events/<int:event_id>")
def update_event(event_id):
    try:
        status_code, body = calendar_service.update_event(
            event_id, request.get_json() or {}
        )
        return jsonify(body), status_code
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@calendar_bp.patch("/events/<int:event_id>/move")
def move_event(event_id):
    try:
        data = request.get_json() or {}
        status_code, body = calendar_service.move_event(
            event_id,
            new_date=data.get("new_date"),
            start_time=data.get("start_time"),
            allow_conflicts=data.get("allow_conflicts", True),
        )
        return jsonify(body), status_code
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@calendar_bp.delete("/events/<int:event_id>")
def delete_event(event_id):
    try:
        status_code, body = calendar_service.delete_event(event_id)
        return jsonify(body), status_code
    except Exception as error:
        return jsonify({"error": str(error)}), 500
