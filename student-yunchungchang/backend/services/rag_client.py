import os

import requests

from services import database_api
from services.rag_documents import build_note_documents


RAG_SERVER_URL = os.getenv(
    "RAG_SERVER_URL",
    "http://127.0.0.1:8012",
).rstrip("/")


def collect_student_notes(student_id: int) -> tuple[list[dict], dict[int, list[dict]]]:
    status_code, notebooks = database_api.list_notebooks(student_id)

    if status_code != 200 or not isinstance(notebooks, list):
        raise RuntimeError("Unable to fetch notebooks for RAG")

    notes_by_notebook = {}

    for notebook in notebooks:
        status_code, notes = database_api.list_notes(notebook["notebook_id"])

        if status_code != 200 or not isinstance(notes, list):
            raise RuntimeError("Unable to fetch notes for RAG")

        notes_by_notebook[notebook["notebook_id"]] = notes

    return notebooks, notes_by_notebook


def answer_note_question(student_id: int, query: str) -> dict:
    notebooks, notes_by_notebook = collect_student_notes(student_id)
    documents = build_note_documents(student_id, notebooks, notes_by_notebook)

    response = requests.post(
        f"{RAG_SERVER_URL}/answer",
        json={
            "query": query,
            "feature": "notebook",
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

    if (
        not isinstance(result.get("answer"), str)
        or not isinstance(result.get("citations"), list)
        or not isinstance(result.get("sources"), list)
        or not isinstance(result.get("confidence"), str)
    ):
        raise RuntimeError("The RAG result is missing required fields")

    return result
