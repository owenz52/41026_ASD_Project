import os
import requests


DATABASE_SERVICE_URL = os.getenv(
    "DATABASE_SERVICE_URL",
    "http://database-service:5002"
)


def get_exams():
    response = requests.get(
        f"{DATABASE_SERVICE_URL}/exams",
        timeout=5
    )
    response.raise_for_status()
    return response.json()


def get_exam_by_id_response(exam_id):
    return requests.get(
        f"{DATABASE_SERVICE_URL}/exams/{exam_id}",
        timeout=5
    )


def get_exams_by_course_response(course_id):
    return requests.get(
        f"{DATABASE_SERVICE_URL}/exams/by-course",
        params={"course_id": course_id},
        timeout=5,
    )


def update_exam_response(exam_id, data):
    return requests.put(
        f"{DATABASE_SERVICE_URL}/exams/{exam_id}",
        json=data,
        timeout=5
    )


def delete_exam_response(exam_id):
    return requests.delete(
        f"{DATABASE_SERVICE_URL}/exams/{exam_id}",
        timeout=5
    )
