
import os

import requests


BACKEND_SERVICE_URL = os.getenv(
    "DATABASE_SERVICE_URL",
    "http://localhost:5009"
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
# TEST EXAMS EXIST
# ==================================================

def test_exams_exist():

    response = requests.get(
        f"{BACKEND_SERVICE_URL}/exams",
        params={"student_id": 1},
        timeout=5
    )

    assert response.status_code == 200

    exams = response.json()

    assert isinstance(exams, list)