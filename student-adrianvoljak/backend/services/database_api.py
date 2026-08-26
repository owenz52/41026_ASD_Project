import requests


DATABASE_BASE_URL = "http://localhost:5001"


def get_assignments(params=None):
    response = requests.get(
        f"{DATABASE_BASE_URL}/assignments",
        params=params,
        timeout=10
    )

    return response.status_code, response.json()


def get_assignment(assignment_id):
    response = requests.get(
        f"{DATABASE_BASE_URL}/assignments/{assignment_id}",
        timeout=10
    )

    return response.status_code, response.json()


def create_assignment(data):
    response = requests.post(
        f"{DATABASE_BASE_URL}/assignments",
        json=data,
        timeout=10
    )

    return response.status_code, response.json()


def update_assignment(assignment_id, data):
    response = requests.put(
        f"{DATABASE_BASE_URL}/assignments/{assignment_id}",
        json=data,
        timeout=10
    )

    return response.status_code, response.json()


def delete_assignment(assignment_id):
    response = requests.delete(
        f"{DATABASE_BASE_URL}/assignments/{assignment_id}",
        timeout=10
    )

    return response.status_code, response.json()


def update_assignment_status(assignment_id, status):
    response = requests.patch(
        f"{DATABASE_BASE_URL}/assignments/{assignment_id}/status",
        json={
            "status": status
        },
        timeout=10
    )

    return response.status_code, response.json()