import requests

from config import DATABASE_SERVICE_URL


def _request(method, path, **kwargs):
    response = requests.request(
        method, f"{DATABASE_SERVICE_URL}{path}", timeout=5, **kwargs
    )
    return response.status_code, response.json()


def list_events(student_id, course_id=None, start_date=None, end_date=None):
    params = {"student_id": student_id}
    if course_id is not None:
        params["course_id"] = course_id
    if start_date is not None:
        params["start_date"] = start_date
    if end_date is not None:
        params["end_date"] = end_date
    return _request("GET", "/events", params=params)


def get_event(event_id):
    return _request("GET", f"/events/{event_id}")


def create_event(data):
    return _request("POST", "/events", json=data)


def update_event(event_id, data):
    return _request("PUT", f"/events/{event_id}", json=data)


def move_event(event_id, data):
    return _request("PATCH", f"/events/{event_id}/move", json=data)


def delete_event(event_id):
    return _request("DELETE", f"/events/{event_id}")


def find_conflicts(student_id, start_time, end_time, exclude_event_id=None):
    params = {
        "student_id": student_id,
        "start_time": start_time,
        "end_time": end_time,
    }
    if exclude_event_id is not None:
        params["exclude_event_id"] = exclude_event_id
    return _request("GET", "/events/conflicts", params=params)
