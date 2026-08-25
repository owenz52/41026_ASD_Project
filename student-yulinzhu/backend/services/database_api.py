import os

import requests


DATABASE_SERVICE_URL = os.getenv("DATABASE_SERVICE_URL", "http://database-service:5002")


def get_courses():
    response = requests.get(f"{DATABASE_SERVICE_URL}/courses", timeout=5)
    response.raise_for_status()
    return response.json()

def get_course( course_id):
    response = requests.get(f"{DATABASE_SERVICE_URL}/courses/{course_id}", timeout=5)
    response.raise_for_status()
    return response.json()

def get_enrolments():
    response = requests.get(f"{DATABASE_SERVICE_URL}/enrolments", timeout=5)
    response.raise_for_status()
    return response.json()

def get_enrolment(enrolment_id):
    response = requests.get(f"{DATABASE_SERVICE_URL}/enrolments/{enrolment_id}", timeout=5)
    response.raise_for_status()
    return response.json()

def get_course_by_code(course_code):
    response = requests.get(f"{DATABASE_SERVICE_URL}/courses/by-code/{course_code}", timeout=5)
    response.raise_for_status()
    return response.json()

def search_courses(keyword):
    response = requests.get(f"{DATABASE_SERVICE_URL}/courses/search", params={"q": keyword}, timeout=5)
    response.raise_for_status()
    return response.json()

def create_enrolment(data):
    response = requests.post(f"{DATABASE_SERVICE_URL}/enrolments", json=data, timeout=5)
    response.raise_for_status()
    return response.json()

def update_enrolment(enrolment_id, data):
    response = requests.put(f"{DATABASE_SERVICE_URL}/enrolments/{enrolment_id}", json=data, timeout=5)
    response.raise_for_status()
    return response.json()

def delete_enrolment(enrolment_id):
    response = requests.delete(f"{DATABASE_SERVICE_URL}/enrolments/{enrolment_id}", timeout=5)
    response.raise_for_status()
    return response.json()