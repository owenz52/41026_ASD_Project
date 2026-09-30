import os

import requests

from services import database_api


RAG_SERVER_URL = os.getenv(
    "RAG_SERVER_URL",
    "http://127.0.0.1:8012",
).rstrip("/")


def build_documents(student_id: int) -> list[dict]:
    status_code, assignments = database_api.get_assignments({
        "student_id": student_id,
    })

    if status_code != 200 or not isinstance(assignments, list):
        raise RuntimeError("Unable to fetch assignments for RAG")

    documents = []

    for assignment in assignments:
        
        if assignment.get("student_id") != student_id:
            continue

        assignment_id = assignment["assignment_id"]
        description = str(assignment.get("description") or "")[:1200]

        text = "\n".join([
            f"Assessment: {assignment.get('title', '')}",
            f"Course: {assignment.get('course_id', '')}",
            f"Due date: {assignment.get('due_date', '')}",
            f"Weighting: {assignment.get('weighting', '')} percent",
            f"Status: {assignment.get('status', '')}",
            f"Completion date: {assignment.get('completion_date') or 'Not recorded'}",
            f"Description: {description}",
        ])

        documents.append({
            "feature": "assessments",
            "student_id": student_id,
            "chunk_id": f"assessment:{assignment_id}",
            "source_id": f"assessment:{assignment_id}",
            "authority_tier": "tier_1",
            "text": text[:2000],
        })

    if len(documents) > 100:
        raise RuntimeError("Assignment context exceeds the RAG document limit")

    return documents


def answer_assessment_question(student_id: int, query: str) -> dict:
    documents = build_documents(student_id)

    response = requests.post(
        f"{RAG_SERVER_URL}/answer",
        json={
            "query": query,
            "feature": "assessments",
            "student_id": student_id,
            "documents": documents,
            "k": 5,
        },
        timeout=75,
    )
    response.raise_for_status()
    result = response.json()

    if not isinstance(result, dict) or result.get("status") not in (
        "success",
        "insufficient_context",
    ):
        raise RuntimeError("The RAG service returned an unexpected result")

    return result