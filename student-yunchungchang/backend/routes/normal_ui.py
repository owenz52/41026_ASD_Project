from flask import Blueprint, jsonify, request

from services import database_api

normal_ui_bp = Blueprint("normal_ui", __name__)


@normal_ui_bp.get("/notebooks")
def notebooks():
    try:
        student_id = request.args.get("student_id")
        course_id = request.args.get("course_id")
        status_code, body = database_api.list_notebooks(student_id, course_id)
        return jsonify(body), status_code
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@normal_ui_bp.get("/notebooks/<int:notebook_id>")
def notebook(notebook_id):
    try:
        status_code, body = database_api.get_notebook(notebook_id)
        return jsonify(body), status_code
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@normal_ui_bp.post("/notebooks")
def create_notebook_route():
    try:
        data = request.get_json(silent=True) or {}
        status_code, body = database_api.create_notebook(data)
        return jsonify(body), status_code
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@normal_ui_bp.put("/notebooks/<int:notebook_id>")
def update_notebook_route(notebook_id):
    try:
        data = request.get_json(silent=True) or {}
        status_code, body = database_api.update_notebook(notebook_id, data)
        return jsonify(body), status_code
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@normal_ui_bp.delete("/notebooks/<int:notebook_id>")
def delete_notebook_route(notebook_id):
    try:
        status_code, body = database_api.delete_notebook(notebook_id)
        return jsonify(body), status_code
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@normal_ui_bp.get("/notebooks/<int:notebook_id>/notes")
def notebook_notes(notebook_id):
    try:
        status_code, body = database_api.list_notes(notebook_id)
        return jsonify(body), status_code
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@normal_ui_bp.get("/notes/<int:note_id>")
def note(note_id):
    try:
        status_code, body = database_api.get_note(note_id)
        return jsonify(body), status_code
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@normal_ui_bp.post("/notes")
def create_note_route():
    try:
        data = request.get_json(silent=True) or {}
        status_code, body = database_api.create_note(data)
        return jsonify(body), status_code
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@normal_ui_bp.put("/notes/<int:note_id>")
def update_note_route(note_id):
    try:
        data = request.get_json(silent=True) or {}
        status_code, body = database_api.update_note(note_id, data)
        return jsonify(body), status_code
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@normal_ui_bp.delete("/notes/<int:note_id>")
def delete_note_route(note_id):
    try:
        status_code, body = database_api.delete_note(note_id)
        return jsonify(body), status_code
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@normal_ui_bp.get("/notes/search")
def search_notes_route():
    try:
        q = request.args.get("q")
        course_id = request.args.get("course_id")
        student_id = request.args.get("student_id")
        status_code, body = database_api.search_notes(q, course_id, student_id)
        return jsonify(body), status_code
    except Exception as error:
        return jsonify({"error": str(error)}), 500
