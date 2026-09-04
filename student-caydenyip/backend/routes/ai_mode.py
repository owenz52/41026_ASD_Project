from flask import Blueprint, request
import requests, json
from services.llm_client import OLLAMA_MODEL, call_architecture_agent, create_chat_completion
from services.prompt_loader import load_prompt
from datetime import datetime


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
    student_id = request.form.get("student_id")

    if not question:
        return "<p>Question is required.</p>", 400

    if not student_id:
        return "<p>Student ID is required.</p>", 400

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
        

        current_datetime = datetime.now().isoformat()

        # Get ONLY this student's exams
        exams_data = get_exams(student_id)

        for exam in exams_data:
            exam.pop('exam_id',None)

        if exams_data:
            student_exam_data = (
                "Student Exam Data:\n"
                + "\n--- EXAM ---\n".join(
            json.dumps(exam, indent=2) for exam in exams_data
        )
    )
        else:
            student_exam_data = "Student has no exams"

        total_exams = len(exams_data)
        uncompleted_exams = sum(1 for exam in exams_data
        if str(exam.get("status", "")).lower() == "uncompleted")

        completed_exams = total_exams - uncompleted_exams

        exam_summary = f"""
        Exam Summary:
        - Total exams: {total_exams}
        - Completed exams: {completed_exams}
        - Uncomplete exams: {uncompleted_exams}
        """
        summary_data = json.dumps(exam_summary, indent=2)



        now = datetime.now()

        upcoming_exams = []

        for exam in exams_data:
            try:
                exam_datetime = datetime.strptime(
                f"{exam['exam_date']} {exam['exam_time']}",
                "%Y-%m-%d %H:%M"
                )

                if (exam.get("status", "").strip().lower() == "uncompleted" and exam_datetime >= now):
                    upcoming_exams.append((exam_datetime, exam))


            except (KeyError, ValueError):
                continue

        upcoming_exams.sort(key=lambda x: x[0])

        next_exam = upcoming_exams[0][1] if upcoming_exams else None

        if next_exam:
            next_exam_text = (
        f"{next_exam['exam_name']} "
        f"on {next_exam['exam_date']} "
        f"at {next_exam['exam_time']} "
        f"(Status: {next_exam['status']})"
    )
        else:
            next_exam_text = "There are no upcoming uncompleted exams."







        

        







        final_prompt = f"""
{task_prompt}

{context_prompt}

EXAM SUMMARY:
{summary_data}

AUTHORITATIVE NEXT UPCOMING EXAM:
{next_exam_text}

STUDENT EXAM DATA:
{student_exam_data}

STUDENT QUESTION:
{question}
"""

        answer = create_chat_completion(
            [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": final_prompt
                },
            ],
            max_tokens=500,
            temperature=0.2,
            model=OLLAMA_MODEL,
        )

        return f"<div class='ai-response'>{answer}</div>", 200


    except requests.RequestException:
        return "<p>Unable to retrieve exam data.</p>", 503

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