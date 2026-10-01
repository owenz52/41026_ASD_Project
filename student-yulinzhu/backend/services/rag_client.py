import os
import requests

from services.database_api import get_courses
from services.rag_documents import build_course_documents

RAG_SERVER_URL = os.getenv(
    "RAG_SERVER_URL",
    "http://127.0.0.1:8012",
).rstrip("/")

def answer_course_question(student_id: int, query: str) -> dict:
    documents = build_course_documents(
        get_courses(),
        student_id,
    )

    response = requests.post(
        f"{RAG_SERVER_URL}/answer",
        json={
            "student_id": student_id,
            "query": query,
            "feature": "enrolment",
            "documents": documents,
            "k": 5,
        },
        timeout=60,
    )
    response.raise_for_status()
    result = response.json()

    if not isinstance(result, dict):
        raise RuntimeError("RAG server returned no structured result")

    if result.get("status") not in {
        "success",
        "insufficient_context",
    }:
        raise RuntimeError("Unexpected RAG status")
    if (
        not isinstance(result.get("answer", str), str)
        or not isinstance(result.get("citations"), list)
        or not isinstance(result.get("sources"), list)
        or not isinstance(result.get("confidence"), str)
    ):
        raise RuntimeError("RAG missing required fields")

    return result
