import json
import re
from flask import Blueprint, request, jsonify

from services.database_api import get_courses, get_course_by_code, search_courses
from services.llm_client import ask_llm
from services.prompt_loader import load_prompt


ai_mode_bp = Blueprint("ai_mode", __name__)


@ai_mode_bp.post("/ask")
def ask_ai():
    data = request.get_json()

    if not data or not data.get("question"):
        return jsonify({"error": "Question is required"}), 400

    question = data.get("question")
    try:
        system_prompt = load_prompt("service/implementation/system_prompt.txt")
        task_prompt = load_prompt("service/implementation/task_prompt.txt")
        context_prompt = load_prompt("service/implementation/context_prompt.txt")

        course_code_match = re.search(r"\b\d{5}\b", question)

        if course_code_match:
            course_code = course_code_match.group()
            course_data = get_course_by_code(course_code)
        else:
            keywords = [
                "art",
                "database",
                "japanese",
                "philosophy",
                "environmental",
                "marketing",
                "cybersecurity",
                "data science",
                "programming",
                "software",
            ]
            matched_keywords = None
            for keyword in keywords:
                if keyword.lower() in question.lower():
                    matched_keywords = keyword
                    break
            if matched_keywords:
                course_data = search_courses(matched_keywords)
            else:
                course_data = get_courses()

        course_data_json = json.dumps(course_data, indent=2)

        user_prompt = f"{task_prompt}\n\n{context_prompt}\n\nCourse Data:\n{course_data_json}\n\nStudent Question:\n{question}"
        answer = ask_llm(system_prompt, user_prompt)
        return jsonify({"answer": answer})
    except Exception as error:
        return jsonify({"error": str(error)}), 500
