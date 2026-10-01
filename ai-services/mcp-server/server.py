import os
from datetime import date, timedelta

import requests
from mcp.server.mcpserver import MCPServer

from typing_extensions import TypedDict


ASSESSMENT_BACKEND_URL = os.getenv(
    "ASSESSMENT_BACKEND_URL",
    "http://127.0.0.1:5007",
).rstrip("/")

ENROLLMENT_BACKEND_URL = os.getenv(
    "ENROLLMENT_BACKEND_URL",
    "http://127.0.0.1:5001",
).rstrip("/")

NOTEBOOK_BACKEND_URL = os.getenv(
    "NOTEBOOK_BACKEND_URL",
    "http://127.0.0.1:5003",
).rstrip("/")

mcp = MCPServer("ASD Shared Tools")

class AssessmentResult(TypedDict):
    assignment_id: int
    title: str
    course_id: int
    due_date: str
    weighting: float | None
    status: str


class UpcomingAssessmentsResult(TypedDict):
    status: str
    as_of: str
    assignments: list[AssessmentResult]

# Assessment Tracker — Adrian Voljak
@mcp.tool()
def assessments_get_upcoming(
    student_id: int,
    days_ahead: int = 14,
) -> UpcomingAssessmentsResult:
    """Return one student's incomplete assessments due within N days."""
    if student_id <= 0:
        raise ValueError("student_id must be positive")

    if not 1 <= days_ahead <= 90:
        raise ValueError("days_ahead must be between 1 and 90")

    response = requests.get(
        f"{ASSESSMENT_BACKEND_URL}/assignments",
        params={
            "student_id": student_id,
            "due": "upcoming",
            "order": "asc",
        },
        timeout=10,
    )
    response.raise_for_status()

    today = date.today()
    last_day = today + timedelta(days=days_ahead)
    assignments = []

    for row in response.json():
        due_date = date.fromisoformat(row["due_date"][:10])

        if (
            row["student_id"] == student_id
            and row["status"] != "completed"
            and today <= due_date <= last_day
        ):
            assignments.append({
                "assignment_id": row["assignment_id"],
                "title": row["title"],
                "course_id": row["course_id"],
                "due_date": row["due_date"],
                "weighting": row.get("weighting"),
                "status": row["status"],
            })

    return {
        "status": "success",
        "as_of": today.isoformat(),
        "assignments": assignments,
    }

#Course Enrollment - Yulin Zhu
class CourseResult(TypedDict):
    course_id: int
    course_name: str
    course_code: str
    description: str
    availability: int

class CoursesResult(TypedDict):
    status: str
    courses: list[CourseResult]

@mcp.tool()
def enrolment_get_courses(available_only: bool = True, ) -> CoursesResult:
    """Read public course information without modifying enrolments."""
    response = requests.get(
        f"{ENROLLMENT_BACKEND_URL}/courses",
        timeout=10,
    )
    response.raise_for_status()
    courses: list[CourseResult] = []
    for row in response.json():
        if available_only and row["availability"] != 1:
            continue
        courses.append({
            "course_id": row["course_id"],
            "course_name": row["course_name"],
            "course_code": row["course_code"],
            "description": row["description"],
            "availability": row["availability"],
        })
    return {
        "status": "success",
        "courses": courses,
    }


# Study Notebook — Yunchung Chang
class NoteResult(TypedDict):
    note_id: int
    notebook_id: int
    course_id: int
    note_title: str
    preview: str
    updated_date: str


class SearchNotesResult(TypedDict):
    status: str
    keyword: str
    notes: list[NoteResult]


@mcp.tool()
def notebooks_search_notes(
    student_id: int,
    keyword: str,
    limit: int = 10,
) -> SearchNotesResult:
    """Search one student's own notes by keyword and return read-only previews."""
    if student_id <= 0:
        raise ValueError("student_id must be positive")

    keyword = keyword.strip()
    if not 1 <= len(keyword) <= 100:
        raise ValueError("keyword must contain 1–100 characters")

    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")

    response = requests.get(
        f"{NOTEBOOK_BACKEND_URL}/notes/search",
        params={"q": keyword, "student_id": student_id},
        timeout=10,
    )
    response.raise_for_status()

    notes = []

    for row in response.json()[:limit]:
        content = row.get("note_content", "")
        notes.append({
            "note_id": row["note_id"],
            "notebook_id": row["notebook_id"],
            "course_id": row["course_id"],
            "note_title": row["note_title"],
            "preview": content[:200],
            "updated_date": row["updated_date"],
        })

    return {
        "status": "success",
        "keyword": keyword,
        "notes": notes,
    }


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8011,
        stateless_http=True,
        json_response=True,
    )