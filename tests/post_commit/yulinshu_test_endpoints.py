import sys
from pathlib import Path
import unittest
from unittest.mock import patch

import requests
from flask import Flask

# Allow tests to import the existing Flask backend modules.
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from routes.normal_ui import normal_ui_bp  # noqa: E402


class EnrolmentEndpointTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(normal_ui_bp)
        self.client = app.test_client()

        self.valid_enrolment = {
            "student_id": 1001,
            "course_id": 1,
            "enrolment_status": "enrolled",
            "enrolment_date": "2026-10-21"
        }

    @patch("routes.normal_ui.get_courses")
    def test_get_courses_success(self, get_courses):
        courses = [{
            "course_id": 1,
            "course_code": "41026",
            "course_name": "Advanced Software Development",
            "description": "Software development with Agent AI",
            "availability": 1,
        }]
        get_courses.return_value = courses
        response = self.client.get("/courses")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), courses)
        get_courses.assert_called_once_with()

    @patch("routes.normal_ui.get_courses")
    def test_get_courses_empty(self, get_courses):
        get_courses.return_value = []

        response = self.client.get("/courses")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    @patch("routes.normal_ui.get_courses")
    def test_get_courses_database_unavailable(self, get_courses):
        get_courses.side_effect = requests.ConnectionError(
            "Database unavailable"
        )

        response = self.client.get("/courses")

        self.assertEqual(response.status_code, 503)
        self.assertIn("error", response.get_json())

    @patch("routes.normal_ui.create_enrolment")
    def test_create_enrolment_success(self, create_enrolment):
        result = {
            "message": "Enrolment created successfully",
            "enrolment_id": 11,
        }
        create_enrolment.return_value = result

        response = self.client.post(
            "/enrolments",
            json=self.valid_enrolment,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json(), result)
        create_enrolment.assert_called_once_with(self.valid_enrolment)

    @patch("routes.normal_ui.create_enrolment")
    def test_create_enrolment_missing_fields(self, create_enrolment):
        response = self.client.post(
            "/enrolments",
            json={"student_id": 1001},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())
        create_enrolment.assert_not_called()

    @patch("routes.normal_ui.create_enrolment")
    def test_create_enrolment_duplicate(self, create_enrolment):
        database_response = requests.Response()
        database_response.status_code = 409
        database_response.headers["Content-Type"] = "application/json"
        database_response._content = (
            b'{"error": "You are already enrolled in this course"}'
        )
        create_enrolment.side_effect = requests.HTTPError(
            "Conflict",
            response=database_response,
        )

        response = self.client.post(
            "/enrolments",
            json=self.valid_enrolment,
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.get_json()["error"],
            "You are already enrolled in this course",
        )


if __name__ == "__main__":
    unittest.main()