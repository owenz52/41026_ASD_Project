from flask import Blueprint, request
import requests, json
from services.llm_client import OLLAMA_MODEL, call_architecture_agent, create_chat_completion
from services.prompt_loader import load_prompt


ai_mode_bp = Blueprint("ai_mode", __name__)


from services.database_api import (
    get_exam_by_id_response,
    get_exams,
    get_exams_by_course_response,
    update_exam_response,
    delete_exam_response,
)



@ai_mode_bp.post("/ask-with-context")
def ask_with_context():
    question = request.form.get("question", "").strip()

    if not question:
        return "<p>Question is required.</p>", 400

    try:
        system_prompt = load_prompt(
            "service/implementation/system_prompt.txt"
        )
        task_prompt = load_prompt(
            "service/implementation/task_prompt.txt"
        )
        context_prompt = load_prompt(
            "service/implementation/context_prompt.txt"
        )

        # Call the existing GET /exams API
        exams_data = get_exams()
        validation_evidence = (
            "GET /exams\n"
            "HTTP 200\n"
            "JSON response:\n"
            f"{json.dumps(exams_data, indent=2)}"
            )


        final_prompt = f"""
{task_prompt}

{context_prompt}

Live Validation Evidence:
{validation_evidence}

User Question:

{question}
"""

        answer = create_chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": final_prompt},
            ],
            max_tokens=300,
            temperature=0.2,
            model=OLLAMA_MODEL,
        )

        return f"<p>{answer}</p>", 200

    except requests.RequestException:
        return "<p>Unable to verify live behavior.</p>", 503

    except Exception as exc:
        return (
            "<p>Context-aware request failed.</p>"
            f"<pre>{exc}</pre>",
            503,
        )

@ai_mode_bp.post("/pattern-selection")
def pattern_selection():
    architecture_request = request.form.get("architecture_request", "").strip()

    if not architecture_request:
        return "<p>Architecture request is required.</p>", 400

    try:
        answer = call_architecture_agent(
            "architecture_system_prompt.txt",
            "pattern_selection_prompt.txt",
            architecture_request,
        )
        return f"<pre>{answer}</pre>", 200
    except Exception as exc:
        return (
            "<p>Pattern selection request failed.</p>"
            f"<pre>{exc}</pre>",
            503,
        )


@ai_mode_bp.post("/architecture-review")
def architecture_review():
    architecture_request = request.form.get("architecture_request", "").strip()

    if not architecture_request:
        return "<p>Architecture request is required.</p>", 400

    try:
        answer = call_architecture_agent(
            "architecture_system_prompt.txt",
            "architecture_task_prompt.txt",
            architecture_request,
        )
        return f"<pre>{answer}</pre>", 200
    except Exception as exc:
        return (
            "<p>Architecture review request failed.</p>"
            f"<pre>{exc}</pre>",
            503,
        )


@ai_mode_bp.post("/adr-review")
def adr_review():
    architecture_request = request.form.get("architecture_request", "").strip()

    if not architecture_request:
        return "<p>ADR text is required.</p>", 400

    try:
        answer = call_architecture_agent(
            "architecture_system_prompt.txt",
            "adr_review_prompt.txt",
            architecture_request,
        )
        return f"<pre>{answer}</pre>", 200
    except Exception as exc:
        return (
            "<p>ADR review request failed.</p>"
            f"<pre>{exc}</pre>",
            503,
        )