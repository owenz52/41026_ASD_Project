"""Release 2 post-commit endpoint tests for the Study Notebook backend.

The database service is mocked, so these tests exercise the backend's own
endpoint functions: request parsing, the call made to the database service,
and how its responses and failures are returned to the frontend.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import requests

# Allow tests to import the existing Flask application.
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import app  # noqa: E402


SAMPLE_NOTEBOOKS = [
    {
        "notebook_id": 1,
        "student_id": 1001,
        "course_id": 1,
        "notebook_title": "ASD Week 9",
        "created_at": "2026-10-01 10:00:00",
    }
]


# --- Endpoint 1: GET /notebooks ------------------------------------------

def test_list_notebooks_returns_database_rows():
    """GET /notebooks returns the student's notebooks for a course."""

    with patch(
        "routes.normal_ui.database_api.list_notebooks",
        return_value=(200, SAMPLE_NOTEBOOKS),
    ) as mock_list:
        with app.test_client() as client:
            response = client.get("/notebooks?student_id=1001&course_id=1")

    assert response.status_code == 200
    assert response.get_json() == SAMPLE_NOTEBOOKS
    mock_list.assert_called_once_with("1001", "1")


def test_list_notebooks_without_filters():
    """GET /notebooks with no query string asks for all notebooks."""

    with patch(
        "routes.normal_ui.database_api.list_notebooks",
        return_value=(200, []),
    ) as mock_list:
        with app.test_client() as client:
            response = client.get("/notebooks")

    assert response.status_code == 200
    assert response.get_json() == []
    mock_list.assert_called_once_with(None, None)


def test_list_notebooks_database_unavailable():
    """GET /notebooks returns a JSON error when the database is down."""

    with patch(
        "routes.normal_ui.database_api.list_notebooks",
        side_effect=requests.ConnectionError("Database unavailable"),
    ):
        with app.test_client() as client:
            response = client.get("/notebooks?student_id=1001")

    assert response.status_code == 500
    assert "error" in response.get_json()


# --- Endpoint 2: POST /notes ---------------------------------------------

NEW_NOTE = {
    "notebook_id": 1,
    "note_title": "Docker networking",
    "note_content": "Containers on one network reach each other by name.",
}


def test_create_note_returns_created_note():
    """POST /notes creates a note inside a notebook."""

    created = {"note_id": 7, **NEW_NOTE}

    with patch(
        "routes.normal_ui.database_api.create_note",
        return_value=(201, created),
    ) as mock_create:
        with app.test_client() as client:
            response = client.post("/notes", json=NEW_NOTE)

    assert response.status_code == 201
    assert response.get_json() == created
    mock_create.assert_called_once_with(NEW_NOTE)


def test_create_note_returns_database_validation_error():
    """POST /notes passes the database's validation error back unchanged."""

    error = {"error": "note_title is required"}

    with patch(
        "routes.normal_ui.database_api.create_note",
        return_value=(400, error),
    ):
        with app.test_client() as client:
            response = client.post("/notes", json={"notebook_id": 1})

    assert response.status_code == 400
    assert response.get_json() == error


def test_create_note_without_json_body_sends_empty_object():
    """POST /notes with a non-JSON body sends an empty object to validate."""

    with patch(
        "routes.normal_ui.database_api.create_note",
        return_value=(400, {"error": "notebook_id is required"}),
    ) as mock_create:
        with app.test_client() as client:
            response = client.post(
                "/notes", data="not json", content_type="text/plain"
            )

    assert response.status_code == 400
    mock_create.assert_called_once_with({})
