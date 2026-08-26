
import requests

from config import ENROLMENT_SERVICE_URL

TIMEOUT = 5


def _get(path, params=None):
    response = requests.get(
        f"{ENROLMENT_SERVICE_URL}{path}", params=params, timeout=TIMEOUT
    )
    return response.status_code, response.json()


def list_courses():
    """All courses in the catalogue. Returns [] if the service is unreachable."""
    try:
        status_code, body = _get("/courses")
        return body if status_code == 200 else []
    except (requests.RequestException, ValueError):
        return []


def get_course(course_id):
    """A single course, or None if missing or unreachable."""
    try:
        status_code, body = _get(f"/courses/{course_id}")
        return body if status_code == 200 else None
    except (requests.RequestException, ValueError):
        return None


def list_enrolments(student_id=None):
    """Enrolment rows, optionally filtered to one student.

    The enrolment service exposes /enrolments without a student filter, so the
    filtering happens here rather than in the query.
    """
    try:
        status_code, body = _get("/enrolments")
        if status_code != 200:
            return []
        if student_id is None:
            return body
        return [
            row for row in body
            if str(row.get("student_id")) == str(student_id)
        ]
    except (requests.RequestException, ValueError):
        return []


def get_enrolled_courses(student_id):
    """Full course records for every course a student is actively enrolled in.

    This is what powers the course dropdown when adding an event: a student
    should only be able to attach an event to a course they actually take.
    """
    enrolments = list_enrolments(student_id)
    active_ids = {
        row["course_id"] for row in enrolments
        if row.get("enrolment_status") == "enrolled"
    }

    if not active_ids:
        return []

    courses = list_courses()
    if courses:
        return [c for c in courses if c["course_id"] in active_ids]

    # Catalogue fetch failed but enrolments succeeded — fall back to
    # per-course lookups so the caller still gets something usable.
    resolved = [get_course(course_id) for course_id in sorted(active_ids)]
    return [course for course in resolved if course is not None]


def is_enrolled(student_id, course_id):
    """Whether a student is actively enrolled in a course.

    Returns False when the enrolment service is unreachable, so callers must
    decide whether that should block an action or just skip enrichment.
    """
    if course_id is None:
        return False
    return any(
        str(row.get("course_id")) == str(course_id)
        and row.get("enrolment_status") == "enrolled"
        for row in list_enrolments(student_id)
    )


def build_course_lookup(course_ids):
    """Map course_id -> course record for the given ids, in one catalogue call.

    Enriching a month of events one HTTP request at a time would be far too
    chatty, so the whole catalogue is fetched once and indexed.
    """
    wanted = {cid for cid in course_ids if cid is not None}
    if not wanted:
        return {}

    courses = list_courses()
    if courses:
        return {c["course_id"]: c for c in courses if c["course_id"] in wanted}

    lookup = {}
    for course_id in sorted(wanted):
        course = get_course(course_id)
        if course is not None:
            lookup[course_id] = course
    return lookup
