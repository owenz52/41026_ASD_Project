import requests

from config import DATABASE_SERVICE_URL


def _request(method, path, **kwargs):
    response = requests.request(
        method, f"{DATABASE_SERVICE_URL}{path}", timeout=5, **kwargs
    )
    return response.status_code, response.json()


def list_notebooks(student_id=None, course_id=None):
    params = {}
    if student_id is not None:
        params["student_id"] = student_id
    if course_id is not None:
        params["course_id"] = course_id
    return _request("GET", "/notebooks", params=params)


def get_notebook(notebook_id):
    return _request("GET", f"/notebooks/{notebook_id}")


def create_notebook(data):
    return _request("POST", "/notebooks", json=data)


def update_notebook(notebook_id, data):
    return _request("PUT", f"/notebooks/{notebook_id}", json=data)


def delete_notebook(notebook_id):
    return _request("DELETE", f"/notebooks/{notebook_id}")


def list_notes(notebook_id):
    return _request("GET", f"/notebooks/{notebook_id}/notes")


def get_note(note_id):
    return _request("GET", f"/notes/{note_id}")


def create_note(data):
    return _request("POST", "/notes", json=data)


def update_note(note_id, data):
    return _request("PUT", f"/notes/{note_id}", json=data)


def delete_note(note_id):
    return _request("DELETE", f"/notes/{note_id}")


def search_notes(q=None, course_id=None):
    params = {}
    if q is not None:
        params["q"] = q
    if course_id is not None:
        params["course_id"] = course_id
    return _request("GET", "/notes/search", params=params)
