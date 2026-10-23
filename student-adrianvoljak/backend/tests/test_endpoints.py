
import sys
from pathlib import Path
from unittest.mock import patch

# Allow tests to import the existing Flask application.
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import app  # noqa: E402


def test_get_assignments():
    """GET /assignments returns assignments successfully."""

    sample_assignments = [
        {
            "id": 1,
            "title": "Architecture Report",
            "status": "pending",
        }
    ]

    with patch(
        "routes.normal_ui.database_api.get_assignments",
        return_value=(200, sample_assignments),
    ) as mock_get:
        with app.test_client() as client:
            response = client.get("/assignments?student_id=1")

    assert response.status_code == 200
    assert response.get_json() == sample_assignments

    mock_get.assert_called_once_with({
        "student_id": "1",
    })


def test_create_assignment():
    """POST /assignments creates an assignment successfully."""

    new_assignment = {
        "title": "Architecture Report",
        "student_id": 1,
        "status": "pending",
    }

    created_assignment = {
        "id": 1,
        **new_assignment,
    }

    with patch(
        "routes.normal_ui.database_api.create_assignment",
        return_value=(201, created_assignment),
    ) as mock_create:
        with app.test_client() as client:
            response = client.post(
                "/assignments",
                json=new_assignment,
            )

    assert response.status_code == 201
    assert response.get_json() == created_assignment

    mock_create.assert_called_once_with(new_assignment)
