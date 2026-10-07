from flask import Blueprint, request, jsonify
import requests
import json
import os

from services.llm_client import (
    OLLAMA_MODEL,
    create_chat_completion,
)
from services.prompt_loader import load_prompt
from services.database_api import get_exams
from datetime import datetime


ai_mode_bp = Blueprint(
    "ai_mode",
    __name__,
)


# ==================================================
# AI MODE CONFIGURATION
# ==================================================

# AI is enabled by default.
#
# Set:
#     AI_ENABLED=false
#
# in Docker/CI to disable AI mode.
AI_ENABLED = os.getenv(
    "AI_ENABLED",
    "true",
).strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)


def ai_disabled_response():
    """
    Standard response returned when AI mode is disabled.
    """

    return jsonify({
        "status": "disabled",
        "message": "AI mode is disabled.",
    }), 503


# ==================================================
# POST /ask-with-context
# ==================================================

@ai_mode_bp.post("/ask-with-context")
def ask_with_context():

    # ------------------------------------------
    # Check AI mode
    # ------------------------------------------

    # If AI_ENABLED=false, stop immediately.
    # This prevents database and LLM calls.
    if not AI_ENABLED:
        return ai_disabled_response()

    # ------------------------------------------
    # Get request data
    # ------------------------------------------

    question = request.form.get(
        "question",
        "",
    ).strip()

    student_id = request.form.get(
        "student_id"
    )

    # ------------------------------------------
    # Validate question
    # ------------------------------------------

    if not question:
        return (
            "<p>Question is required.</p>",
            400,
        )

    # ------------------------------------------
    # Validate student ID
    # ------------------------------------------

    if not student_id:
        return (
            "<p>Student ID is required.</p>",
            400,
        )

    # ------------------------------------------
    # AI request
    # ------------------------------------------

    try:

        # --------------------------------------
        # Load prompts
        # --------------------------------------

        system_prompt = load_prompt(
            "service/implementation/system_prompt.txt"
        )

        task_prompt = load_prompt(
            "service/implementation/task_prompt.txt"
        )

        context_prompt = load_prompt(
            "service/implementation/context_prompt.txt"
        )

        # --------------------------------------
        # Current date/time
        # --------------------------------------

        current_datetime = datetime.now().isoformat()

        # --------------------------------------
        # Get ONLY this student's exams
        # --------------------------------------

        exams_data = get_exams(
            student_id
        )

        # Remove exam IDs from the AI context.
        for exam in exams_data:
            exam.pop(
                "exam_id",
                None,
            )

        # --------------------------------------
        # Build student exam data
        # --------------------------------------

        if exams_data:

            student_exam_data = (
                "Student Exam Data:\n"
                + "\n--- EXAM ---\n".join(
                    json.dumps(
                        exam,
                        indent=2,
                    )
                    for exam in exams_data
                )
            )

        else:

            student_exam_data = (
                "Student has no exams"
            )

        # --------------------------------------
        # Exam summary
        # --------------------------------------

        total_exams = len(
            exams_data
        )

        uncompleted_exams = sum(
            1
            for exam in exams_data
            if str(
                exam.get(
                    "status",
                    "",
                )
            ).lower() == "uncompleted"
        )

        completed_exams = (
            total_exams
            - uncompleted_exams
        )

        exam_summary = f"""
        Exam Summary:
        - Total exams: {total_exams}
        - Completed exams: {completed_exams}
        - Uncomplete exams: {uncompleted_exams}
        """

        summary_data = json.dumps(
            exam_summary,
            indent=2,
        )

        # --------------------------------------
        # Find upcoming exams
        # --------------------------------------

        now = datetime.now()

        upcoming_exams = []

        for exam in exams_data:

            try:

                exam_datetime = datetime.strptime(
                    f"{exam['exam_date']} "
                    f"{exam['exam_time']}",
                    "%Y-%m-%d %H:%M",
                )

                if (
                    exam.get(
                        "status",
                        "",
                    ).strip().lower()
                    == "uncompleted"
                    and exam_datetime >= now
                ):
                    upcoming_exams.append(
                        (
                            exam_datetime,
                            exam,
                        )
                    )

            except (
                KeyError,
                ValueError,
            ):
                continue

        upcoming_exams.sort(
            key=lambda x: x[0]
        )

        next_exam = (
            upcoming_exams[0][1]
            if upcoming_exams
            else None
        )

        # --------------------------------------
        # Build next exam text
        # --------------------------------------

        if next_exam:

            next_exam_text = (
                f"{next_exam['exam_name']} "
                f"on {next_exam['exam_date']} "
                f"at {next_exam['exam_time']} "
                f"(Status: "
                f"{next_exam['status']})"
            )

        else:

            next_exam_text = (
                "There are no upcoming "
                "uncompleted exams."
            )

        # --------------------------------------
        # Build final prompt
        # --------------------------------------

        final_prompt = f"""
{task_prompt}

{context_prompt}

CURRENT DATE AND TIME:
{current_datetime}

EXAM SUMMARY:
{summary_data}

AUTHORITATIVE NEXT UPCOMING EXAM:
{next_exam_text}

STUDENT EXAM DATA:
{student_exam_data}

STUDENT QUESTION:
{question}
"""

        # --------------------------------------
        # Call LLM
        # --------------------------------------

        answer = create_chat_completion(
            [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": final_prompt,
                },
            ],
            max_tokens=300,
            temperature=0,
            model=OLLAMA_MODEL,
        )

        # --------------------------------------
        # Return AI response
        # --------------------------------------

        return (
            f"<div class='ai-response'>"
            f"{answer}"
            f"</div>",
            200,
        )

    # ------------------------------------------
    # Request/service errors
    # ------------------------------------------

    except requests.RequestException:

        return (
            "<p>Unable to retrieve "
            "exam data.</p>",
            503,
        )

    # ------------------------------------------
    # Unexpected errors
    # ------------------------------------------

    except Exception as exc:

        return (
            "<p>Context-aware request failed.</p>"
            f"<pre>{exc}</pre>",
            503,
        )
