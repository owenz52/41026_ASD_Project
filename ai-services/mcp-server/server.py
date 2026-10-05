import os
from datetime import date, timedelta

import requests
from mcp.server.mcpserver import MCPServer

from typing_extensions import TypedDict

from tools_caydenyip import (

    get_student_exam_status,
    get_student_exams,
    get_student_exam_summary,
)


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

CALENDAR_DATABASE_URL = os.getenv(
    "CALENDAR_DATABASE_URL",
    "http://127.0.0.1:5006",
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

#========================================
#=============Exams Tools================
#========================================
@mcp.tool()
def student_exam_status(student_id: int):
    """Get the number of completed and non-completed exams."""
    return get_student_exam_status(student_id)


@mcp.tool()
def student_exams(student_id: int):
    """Get all active exams belonging to a student."""
    return get_student_exams(student_id)


@mcp.tool()
def student_exam_summary(student_id: int):
    """
    Get a complete student exam summary including
    student information, subjects, exam counts and exams.
    """
    return get_student_exam_summary(student_id)

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


# ----------------------------------------------------------------------
# Calendar — Voreak Sanith
#
# READ-ONLY and student-scoped. The tool only ever GETs from the calendar
# database service, the calendar's published data API. It does not call the
# calendar backend, which requires a signed-in session that a service-to-
# service call does not have. It never creates, changes or deletes an event,
# and it drops any row that does not belong to the requested student_id.
# ----------------------------------------------------------------------
class CalendarEvent(TypedDict):
    event_id: int
    title: str
    event_type: str
    subject: str | None
    start_time: str
    end_time: str
    location: str | None


class UpcomingEventsResult(TypedDict):
    status: str
    as_of: str
    days_ahead: int
    count: int
    events: list[CalendarEvent]


@mcp.tool()
def calendar_get_upcoming_events(
    student_id: int,
    days_ahead: int = 7,
) -> UpcomingEventsResult:
    """Return one student's calendar events starting within N days (1-60)."""
    if student_id <= 0:
        raise ValueError("student_id must be positive")

    if not 1 <= days_ahead <= 60:
        raise ValueError("days_ahead must be between 1 and 60")

    today = date.today()

    response = requests.get(
        f"{CALENDAR_DATABASE_URL}/events",
        params={
            "student_id": student_id,
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=days_ahead)).isoformat(),
        },
        timeout=10,
    )
    response.raise_for_status()

    body = response.json()
    # The database service returns a bare list; accept a wrapped one as well.
    rows = body.get("events", []) if isinstance(body, dict) else body

    events: list[CalendarEvent] = []
    for row in rows:
        # Defence in depth: never return another student's row.
        if row.get("student_id") != student_id:
            continue
        events.append({
            "event_id": row["event_id"],
            "title": row["title"],
            "event_type": row["event_type"],
            "subject": row.get("subject"),
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "location": row.get("location"),
        })

    return {
        "status": "success",
        "as_of": today.isoformat(),
        "days_ahead": days_ahead,
        "count": len(events),
        "events": events,
    }


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8011,
        stateless_http=True,
        json_response=True,
    )