import os

import requests


BACKEND_SERVICE_URL = os.getenv(
    "DATABASE_SERVICE_URL",
    "http://localhost:5009"
)

ENROLMENT_DATABASE_URL = os.getenv(
    "ENROLMENT_DATABASE_URL",
    "http://localhost:5002"
)


# ==================================================
# TEST HEALTH CHECK
# ==================================================

def test_service_health():

    response = requests.get(
        f"{BACKEND_SERVICE_URL}/",
        timeout=5
    )

    assert response.status_code == 200

    data = response.json()

    assert data["service"] == "exam-backend"
    assert data["status"] == "running"


# ==================================================
# TEST EXAM GET
# ==================================================

def test_exams_exist():

    # Create an enrolment for student 1 in course 1
    enrolment_response = requests.post(
        f"{ENROLMENT_DATABASE_URL}/enrolments",
        json={
            "student_id": 1,
            "course_id": 1,
            "enrolment_status": "Enrolled",
            "enrolment_date": "2026-10-27"
        },
        timeout=5
    )

    assert enrolment_response.status_code == 201, (
        f"Failed to create enrolment: "
        f"{enrolment_response.text}"
    )

    # Request exams for the enrolled student
    response = requests.get(
        f"{BACKEND_SERVICE_URL}/exams",
        params={"student_id": 1},
        timeout=5
    )

    assert response.status_code == 200

    exams = response.json()

    assert isinstance(exams, list)

    assert any(
        exam["exam_name"] == "41026 Final Exam"
        for exam in exams
    ), "41026 Final Exam was not returned"