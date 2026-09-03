"""Read-only clients for other teams' database services.

The calendar pulls upcoming deadlines from the assessment tracker and the exam
timetable. Both are other students' services: this module only ever performs
GET requests against endpoints that already exist, and never writes.

Every function returns a safe fallback instead of raising, so the calendar
keeps working when a source is unavailable. A missing service means "no
deadlines from there", not a broken page.
"""
import requests

from config import ASSESSMENT_SERVICE_URL, EXAM_SERVICE_URL

TIMEOUT = 5


def _get(base_url, path, params=None):
    response = requests.get(f"{base_url}{path}", params=params, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


# ------------------------------------------------------------- assessments

def list_assignments(student_id=None, status=None):
    """Assignments from the assessment tracker.

    The service exposes /assignments with optional student_id and status
    filters. Returns [] if it is unreachable.
    """
    params = {}
    if student_id is not None:
        params["student_id"] = student_id
    if status is not None:
        params["status"] = status

    try:
        body = _get(ASSESSMENT_SERVICE_URL, "/assignments", params)
        return body if isinstance(body, list) else body.get("assignments", [])
    except (requests.RequestException, ValueError):
        return []


def assessment_service_available():
    """Whether the assessment service answered successfully.

    A 5xx counts as unavailable: the service is reachable but not serving, and
    treating that as "available with no assignments" would wrongly tell the
    student they have nothing due.
    """
    try:
        response = requests.get(
            f"{ASSESSMENT_SERVICE_URL}/assignments", timeout=TIMEOUT
        )
        return response.status_code < 400
    except requests.RequestException:
        return False


# --------------------------------------------------------------------- exams

def list_exams(student_id=None):
    """Exams from the exam timetable service.

    The service exposes /exams. It has no student filter, so filtering happens
    here rather than in the query.
    """
    try:
        body = _get(EXAM_SERVICE_URL, "/exams")
        exams = body if isinstance(body, list) else body.get("exams", [])
    except (requests.RequestException, ValueError):
        return []

    if student_id is None:
        return exams

    return [
        exam for exam in exams
        if str(exam.get("student_id")) == str(student_id)
    ]


def exam_service_available():
    """Whether the exam service answered successfully. See the note above."""
    try:
        response = requests.get(f"{EXAM_SERVICE_URL}/exams", timeout=TIMEOUT)
        return response.status_code < 400
    except requests.RequestException:
        return False


# ------------------------------------------------------------ normalisation

def normalise_assignments(assignments):
    """Reduce assignment rows to the shape the calendar cares about.

    `due_date` is a date with no time, so a due item is treated as falling at
    the end of that day.
    """
    items = []
    for row in assignments:
        due = str(row.get("due_date") or "").strip()
        if not due:
            continue

        items.append({
            "source": "assessment",
            "source_id": row.get("assignment_id"),
            "title": row.get("title") or "Assignment",
            "subject": str(row.get("course_id") or "") or None,
            "due": f"{due[:10]} 23:59",
            "weighting": float(row.get("weighting") or 0),
            "status": row.get("status") or "not_started",
        })
    return items


def normalise_exams(exams):
    """Reduce exam rows to the same shape, combining date and time."""
    items = []
    for row in exams:
        date = str(row.get("exam_date") or "").strip()
        if not date:
            continue

        time = str(row.get("exam_time") or "09:00").strip()[:5]
        if len(time) < 5:
            time = "09:00"

        items.append({
            "source": "exam",
            "source_id": row.get("exam_id"),
            "title": row.get("exam_name") or "Exam",
            "subject": str(row.get("course_id") or "") or None,
            "due": f"{date[:10]} {time}",
            # Exams carry no weighting; they are treated as high-stakes so the
            # planner does not rank them below a large assignment.
            "weighting": 50.0,
            "status": row.get("status") or "Uncompleted",
        })
    return items


def collect_deadlines(student_id):
    """All upcoming assessable items from both services, in one shape.

    Returns (items, sources) where sources records which services answered, so
    callers can tell "nothing due" apart from "service down".
    """
    assignments = list_assignments(student_id)
    exams = list_exams(student_id)

    sources = {
        "assessments": {
            "available": bool(assignments) or assessment_service_available(),
            "count": len(assignments),
        },
        "exams": {
            "available": bool(exams) or exam_service_available(),
            "count": len(exams),
        },
    }

    items = normalise_assignments(assignments) + normalise_exams(exams)
    items.sort(key=lambda item: item["due"])
    return items, sources
