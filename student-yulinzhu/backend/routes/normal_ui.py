from flask import Blueprint, jsonify, request

from services.database_api import get_courses, get_course, get_enrolments, get_enrolment, create_enrolment, update_enrolment, delete_enrolment

normal_ui_bp = Blueprint("normal_ui", __name__)

@normal_ui_bp.get("/courses")
def courses():
    try:
        data = get_courses()
        return jsonify(data)
    except Exception as error:
        return jsonify({
            "error": str(error),
        }), 500

@normal_ui_bp.get("/courses/<int:course_id>")
def course(course_id):
    try:
        data = get_course(course_id)
        return jsonify(data)
    except Exception as error:
        return jsonify({
            "error": str(error),
        }), 500

@normal_ui_bp.get("/enrolments")
def enrolments():
    try:
        data = get_enrolments()
        return jsonify(data)
    except Exception as error:
        return jsonify({
            "error": str(error),
        }), 500

@normal_ui_bp.get("/enrolments/<int:enrolment_id>")
def enrolment(enrolment_id):
    try:
        data = get_enrolment(enrolment_id)
        return jsonify(data)
    except Exception as error:
        return jsonify({
            "error": str(error),
        }), 500

@normal_ui_bp.post("/enrolments")
def create_enrolment_route():
    try:
        data = request.get_json()
        result = create_enrolment(data)
        return jsonify(result)
    except Exception as error:
        return jsonify({
            "error": str(error),
        }), 500

@normal_ui_bp.put("/enrolments/<int:enrolment_id>")
def update_enrolment_route(enrolment_id):
    try:
        data = request.get_json()
        result = update_enrolment(enrolment_id, data)
        return jsonify(result)
    except Exception as error:
        return jsonify({
            "error": str(error),
        }), 500

@normal_ui_bp.delete("/enrolments/<int:enrolment_id>")
def delete_enrolment_route(enrolment_id):
    try:
        result = delete_enrolment(enrolment_id)
        return jsonify(result)
    except Exception as error:
        return jsonify({
            "error": str(error),
        }), 500