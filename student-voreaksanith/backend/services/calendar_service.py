"""Business logic for the calendar feature.

Routes stay thin: they read parameters and call one function here. All course
cross-referencing, validation and conflict checking happens in this module.
"""
from datetime import datetime

from services import database_api, enrolment_api

TIME_FORMAT = "%Y-%m-%d %H:%M"

# Event types the calendar understands, with the colour the frontend uses.
EVENT_TYPES = {
    "lecture": "#3366CC",
    "seminar": "#3366CC",
    "lab": "#3366CC",
    "deadline": "#DC3545",
    "exam": "#FF6B6B",
    "revision": "#1A1A1A",
    "office_hours": "#666666",
    "other": "#999999",
}


def _decorate(event, course_lookup=None):
    """Attach display colour and course details to a raw database row."""
    event = dict(event)
    event["color"] = EVENT_TYPES.get(event.get("event_type"), EVENT_TYPES["other"])

    course_id = event.get("course_id")
    course = (course_lookup or {}).get(course_id)

    if course:
        event["course_code"] = course.get("course_code")
        event["course_name"] = course.get("course_name")
    else:
        # Either the event has no course, or the enrolment service is
        # unavailable. Both are non-fatal; the event still renders.
        event["course_code"] = None
        event["course_name"] = None

    return event


def _parse(value):
    return datetime.strptime(value.replace("T", " ")[:16], TIME_FORMAT)


def list_events(student_id, course_id=None, start_date=None, end_date=None):
    """Events for a student, enriched with course code and name."""
    status_code, body = database_api.list_events(
        student_id, course_id, start_date, end_date
    )
    if status_code != 200:
        return status_code, body

    lookup = enrolment_api.build_course_lookup(
        [event.get("course_id") for event in body]
    )
    events = [_decorate(event, lookup) for event in body]

    return 200, {"events": events, "count": len(events)}


def get_event(event_id):
    status_code, body = database_api.get_event(event_id)
    if status_code != 200:
        return status_code, body

    lookup = enrolment_api.build_course_lookup([body.get("course_id")])
    return 200, _decorate(body, lookup)


def add_event(data):
    """Create an event, validating its type and course link first."""
    event_type = data.get("event_type")
    if event_type and event_type not in EVENT_TYPES:
        return 400, {
            "error": f"Unknown event_type '{event_type}'. "
                     f"Valid types: {', '.join(sorted(EVENT_TYPES))}"
        }

    student_id = data.get("student_id")
    course_id = data.get("course_id")

    # A course-linked event only makes sense if the student takes that course.
    # If the enrolment service is unreachable we allow the event through rather
    # than blocking the student, but flag it so the response is honest.
    enrolment_unavailable = False
    if course_id:
        if not enrolment_api.is_enrolled(student_id, course_id):
            if enrolment_api.list_enrolments(student_id):
                return 400, {
                    "error": "Student is not enrolled in the specified course"
                }
            enrolment_unavailable = True

    status_code, body = database_api.create_event(data)
    if status_code != 201:
        return status_code, body

    lookup = enrolment_api.build_course_lookup([body.get("course_id")])
    event = _decorate(body, lookup)

    if enrolment_unavailable:
        event["warning"] = (
            "Course link could not be verified; enrolment service unavailable"
        )

    return 201, event


def update_event(event_id, data):
    event_type = data.get("event_type")
    if event_type and event_type not in EVENT_TYPES:
        return 400, {"error": f"Unknown event_type '{event_type}'"}

    status_code, body = database_api.update_event(event_id, data)
    if status_code != 200:
        return status_code, body

    lookup = enrolment_api.build_course_lookup([body.get("course_id")])
    return 200, _decorate(body, lookup)


def move_event(event_id, new_date=None, start_time=None, allow_conflicts=True):
    """Reschedule an event, preserving its duration.

    Called when a student drags an event to a different day. Overlapping
    events are reported back but permitted by default, since a student may
    legitimately have two things booked at once.
    """
    if not new_date and not start_time:
        return 400, {"error": "new_date or start_time is required"}

    status_code, existing = database_api.get_event(event_id)
    if status_code != 200:
        return status_code, existing

    status_code, moved = database_api.move_event(
        event_id, {"new_date": new_date, "start_time": start_time}
    )
    if status_code != 200:
        return status_code, moved

    conflict_status, conflicts = database_api.find_conflicts(
        moved["student_id"],
        moved["start_time"],
        moved["end_time"],
        exclude_event_id=event_id,
    )

    lookup = enrolment_api.build_course_lookup([moved.get("course_id")])
    event = _decorate(moved, lookup)

    if conflict_status == 200 and conflicts:
        if not allow_conflicts:
            # Put it back where it was before reporting the clash.
            database_api.move_event(
                event_id, {"start_time": existing["start_time"]}
            )
            return 409, {
                "error": "Move would clash with an existing event",
                "conflicts": conflicts,
            }
        event["conflicts"] = [
            {
                "event_id": c["event_id"],
                "title": c["title"],
                "start_time": c["start_time"],
            }
            for c in conflicts
        ]

    event["moved_from"] = existing["start_time"]
    return 200, event


def delete_event(event_id):
    return database_api.delete_event(event_id)


def get_course_options(student_id):
    """Courses a student can attach an event to, for the add-event dropdown."""
    courses = enrolment_api.get_enrolled_courses(student_id)
    return 200, {
        "courses": [
            {
                "course_id": c["course_id"],
                "course_code": c["course_code"],
                "course_name": c["course_name"],
            }
            for c in courses
        ],
        "count": len(courses),
        "enrolment_service_available": bool(courses)
        or bool(enrolment_api.list_courses()),
    }


def get_course_schedule(student_id, course_id):
    """Every calendar event for one course, plus that course's details."""
    course = enrolment_api.get_course(course_id)
    status_code, body = database_api.list_events(student_id, course_id=course_id)

    if status_code != 200:
        return status_code, body

    lookup = {course["course_id"]: course} if course else {}
    events = [_decorate(event, lookup) for event in body]

    return 200, {
        "course": course,
        "events": events,
        "count": len(events),
    }
