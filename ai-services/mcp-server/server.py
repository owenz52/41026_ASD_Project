import os
from datetime import date, timedelta

import requests
from mcp.server.mcpserver import MCPServer

from typing_extensions import TypedDict


ASSESSMENT_BACKEND_URL = os.getenv(
    "ASSESSMENT_BACKEND_URL",
    "http://127.0.0.1:5007",
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


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8011,
        stateless_http=True,
        json_response=True,
    )