from flask import Blueprint, jsonify, request, current_app
import requests
from services.database_api import get_courses, get_course, get_enrolments, get_enrolment, create_enrolment, update_enrolment, delete_enrolment

normal_ui_bp = Blueprint("normal_ui", __name__)

@normal_ui_bp.get("/courses")
def courses():
    try:
        data = get_courses()
        return jsonify(data), 200
    except (requests.ConnectionError, requests.Timeout):
        return jsonify({
            "error": "Database service is unavailable",
        }), 503
    except requests.RequestException:
        current_app.logger.exception("Course database request failed")
        return jsonify({
            "error": "Unable to retrieve courses from database",
        }), 502
    except Exception:
        current_app.logger.exception("Unexpected course lookup failure")
        return jsonify({
            "error": "Unable to retrieve courses",
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
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "A JSON object is required",
        }), 400

    required_fields = (
        "student_id",
        "course_id",
        "enrolment_status",
        "enrolment_date",
    )

    if any(
        field not in data or data[field] is None or data[field] == ""
        for field in required_fields
    ):
        return jsonify({
            "error": "Missing required fields",
        }), 400

    for field in ("student_id", "course_id"):
        if type(data[field]) is not int or data[field] <= 0:
            return jsonify({
                "error": f"{field} must be a positive integer",
            }), 400

    for field in ("enrolment_status", "enrolment_date"):
        if not isinstance(data[field], str) or not data[field].strip():
            return jsonify({
                "error": f"{field} must be a non-empty string",
            }), 400

    try:
        result = create_enrolment(data)
        return jsonify(result), 201

    except requests.HTTPError as error:
        response = error.response

        # Preserve expected database validation errors.
        if response is not None and response.status_code in {400, 404, 409}:
            messages = {
                400: "Invalid enrolment data",
                404: "Course not found",
                409: "You are already enrolled in this course",
            }
            return jsonify({
                "error": messages[response.status_code],
            }), response.status_code

        current_app.logger.exception("Database rejected enrolment creation")
        return jsonify({
            "error": "Unable to create enrolment through database service",
        }), 502

    except (requests.ConnectionError, requests.Timeout):
        return jsonify({
            "error": "Database service is unavailable",
        }), 503

    except requests.RequestException:
        current_app.logger.exception("Enrolment database request failed")
        return jsonify({
            "error": "Unable to contact database service",
        }), 502

    except Exception:
        current_app.logger.exception("Unexpected enrolment creation failure")
        return jsonify({
            "error": "Unable to create enrolment",
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