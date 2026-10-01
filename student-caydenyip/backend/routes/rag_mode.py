from flask import Blueprint, request
import requests

from services.rag_api import call_rag_service
from services.database_api import (
    get_exams,
    get_student_enrolments,
)


rag_bp = Blueprint("rag_mode", __name__)


# ==================================================
# CONVERT EXAM TO RAG DOCUMENT
# ==================================================

def exam_to_rag_document(exam: dict, student_id: int) -> dict:
    """
    Convert a database exam record into the standard
    document format expected by the shared RAG service.
    """

    if not isinstance(exam, dict):
        raise ValueError("Each exam must be an object")

    if "exam_id" not in exam:
        raise ValueError("Exam is missing exam_id")

    exam_id = str(exam["exam_id"])

    text_parts = []

    if exam.get("exam_name"):
        text_parts.append(
            f"Exam: {exam['exam_name']}"
        )

    if exam.get("course_id") is not None:
        text_parts.append(
            f"Course ID: {exam['course_id']}"
        )

    if exam.get("exam_date"):
        text_parts.append(
            f"Date: {exam['exam_date']}"
        )

    if exam.get("exam_time"):
        text_parts.append(
            f"Time: {exam['exam_time']}"
        )

    text = ". ".join(text_parts)

    if not text:
        raise ValueError(
            f"Exam {exam_id} does not contain usable information"
        )

    return {
        "chunk_id": f"exam-{student_id}-{exam_id}",
        "source_id": f"exam-{exam_id}",
        "text": text,
        "feature": "student",
        "student_id": student_id,
        "authority_tier": "tier_1",
    }


# ==================================================
# GET STUDENT RAG DOCUMENTS
# ==================================================

def get_student_rag_documents(student_id: int) -> list[dict]:
    """
    Get exams belonging to the student and convert them
    into the standard RAG document format.
    """

    exams = get_exams(student_id)

    if not isinstance(exams, list):
        raise ValueError(
            "Database service must return a list of exams"
        )

    return [
        exam_to_rag_document(exam, student_id)
        for exam in exams
    ]


# ==================================================
# GET STUDENT ID
# ==================================================

def get_student_id():
    student_id = request.form.get("student_id")

    if student_id is None:
        return None, {
            "status": "error",
            "error": "student_id is required",
        }, 400

    try:
        student_id = int(student_id)
    except (TypeError, ValueError):
        return None, {
            "status": "error",
            "error": "student_id must be an integer",
        }, 400

    if student_id <= 0:
        return None, {
            "status": "error",
            "error": "student_id must be greater than zero",
        }, 400

    return student_id, None, None


# ==================================================
# BUILD RAG PAYLOAD
# ==================================================

def build_rag_payload():
    """
    Validate the Flask request, retrieve the student's
    enrolments and exams, and construct the shared RAG
    request payload.
    """

    student_id, error, status = get_student_id()

    if error:
        return None, error, status

    query = request.form.get(
        "query",
        ""
    ).strip()

    if not query:
        return None, {
            "status": "error",
            "error": "query is required",
        }, 400

    if len(query) > 1000:
        return None, {
            "status": "error",
            "error": "query must contain at most 1000 characters",
        }, 400

    try:
        k = int(
            request.form.get(
                "k",
                "5"
            )
        )
    except (TypeError, ValueError):
        return None, {
            "status": "error",
            "error": "k must be an integer",
        }, 400

    if not 1 <= k <= 10:
        return None, {
            "status": "error",
            "error": "k must be between 1 and 10",
        }, 400

    # --------------------------------------------------
    # GET STUDENT ENROLMENTS
    # --------------------------------------------------

    try:
        enrolments = get_student_enrolments(
            student_id
        )
    except requests.Timeout:
        return None, {
            "status": "error",
            "error": "Enrolment service timed out",
        }, 503
    except requests.RequestException:
        return None, {
            "status": "error",
            "error": "Enrolment service unavailable",
        }, 503

    if not isinstance(enrolments, list):
        return None, {
            "status": "error",
            "error": "Enrolment service must return a list",
        }, 502

    # --------------------------------------------------
    # GET STUDENT EXAMS
    # --------------------------------------------------

    try:
        documents = get_student_rag_documents(
            student_id
        )
    except requests.Timeout:
        return None, {
            "status": "error",
            "error": "Database service timed out",
        }, 503
    except requests.RequestException:
        return None, {
            "status": "error",
            "error": "Database service unavailable",
        }, 503
    except ValueError as exc:
        return None, {
            "status": "error",
            "error": str(exc),
        }, 502

    if len(documents) > 100:
        return None, {
            "status": "error",
            "error": "Too many student documents",
        }, 400

    # --------------------------------------------------
    # BUILD RAG PAYLOAD
    # --------------------------------------------------

    payload = {
        "query": query,
        "feature": "student",
        "student_id": student_id,
        "enrolments": enrolments,
        "documents": documents,
        "k": k,
    }

    return payload, None, None


# ==================================================
# CALL RAG SERVICE
# ==================================================

def run_rag_request(path: str, payload: dict):
    """
    Call the shared RAG service and translate connection
    failures into Flask responses.
    """

    try:
        result = call_rag_service(
            path,
            payload
        )

        return result, 200

    except requests.Timeout:
        return {
            "status": "error",
            "error": "RAG service timed out",
        }, 504

    except requests.HTTPError as exc:
        response = exc.response

        if response is not None:
            try:
                data = response.json()
            except ValueError:
                data = None

            if data:
                return data, response.status_code

        return {
            "status": "error",
            "error": "RAG service request failed",
        }, 502

    except requests.RequestException:
        return {
            "status": "error",
            "error": "RAG service unavailable",
        }, 503


# ==================================================
# POST /rag/retrieve
# ==================================================

@rag_bp.post("/rag/retrieve")
def rag_retrieve():

    payload, error, status = build_rag_payload()

    if error:
        return error, status

    return run_rag_request(
        "/retrieve",
        payload
    )


# ==================================================
# POST /rag/answer
# ==================================================

@rag_bp.post("/rag/answer")
def rag_answer():

    payload, error, status = build_rag_payload()

    if error:
        return error, status

    return run_rag_request(
        "/answer",
        payload
    )
