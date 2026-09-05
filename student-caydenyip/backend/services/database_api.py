import os
import requests


DATABASE_SERVICE_URL = os.getenv(
    "DATABASE_SERVICE_URL",
    "http://exam-database:5010"
)

ENROLMENT_SERVICE_URL = os.getenv(
    "ENROLMENT_SERVICE_URL",
    "http://enrolment-database:5002"
)


# ==================================================
# GET STUDENT ENROLMENTS
# ==================================================

def get_student_enrolments(student_id):

    response = requests.get(
        f"{ENROLMENT_SERVICE_URL}/enrolments/by-student/{student_id}",
        timeout=5
    )

    response.raise_for_status()

    return response.json()


# ==================================================
# GET EXAMS
# ==================================================

def get_exams(student_id):

    response = requests.get(
        f"{DATABASE_SERVICE_URL}/exams",
        params={
            "student_id": student_id
        },
        timeout=5
    )

    response.raise_for_status()

    return response.json()


# ==================================================
# GET EXAM BY ID
# ==================================================

def get_exam_by_id_response(exam_id):

    return requests.get(
        f"{DATABASE_SERVICE_URL}/exams/{exam_id}",
        timeout=5
    )


# ==================================================
# GET EXAMS BY COURSE
# ==================================================

def get_exams_by_course_response(course_id):

    return requests.get(
        f"{DATABASE_SERVICE_URL}/exams/by-course",
        params={
            "course_id": course_id
        },
        timeout=5
    )


# ==================================================
# UPDATE EXAM
# ==================================================

def update_exam_response(exam_id, data):

    return requests.put(
        f"{DATABASE_SERVICE_URL}/exams/{exam_id}",
        json=data,
        timeout=5
    )


# ==================================================
# DELETE EXAM
# ==================================================

def delete_exam_response(exam_id):

    return requests.delete(
        f"{DATABASE_SERVICE_URL}/exams/{exam_id}",
        timeout=5
    )


# ==================================================
# RESET EXAMS FOR STUDENT
# ==================================================

def reset_exams_response(student_id, course_ids):

    return requests.post(
        f"{DATABASE_SERVICE_URL}/exams/reset",
        params={
            "student_id": student_id
        },
        json={
            "student_id": student_id,
            "course_ids": course_ids
        },
        timeout=5
    )


# ==================================================
# SYNC STUDENT EXAMS
# ==================================================

def sync_exams_response(student_id, course_ids):

    return requests.post(
        f"{DATABASE_SERVICE_URL}/exams/sync",
        params={
            "student_id": student_id
        },
        json={
            "course_ids": course_ids
        },
        timeout=5
    )


# ==================================================
# ADD EXAM
# ==================================================

def add_exam_response(
    student_id,
    course_id,
    exam_name,
    exam_date,
    exam_time
):

    data = {
        "student_id": student_id,
        "course_id": course_id,
        "exam_name": exam_name,
        "exam_date": exam_date,
        "exam_time": exam_time
    }

    response = requests.post(
        f"{DATABASE_SERVICE_URL}/exams",
        json=data,
        timeout=5
    )

    return response