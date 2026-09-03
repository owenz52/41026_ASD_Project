"""Business logic for the calendar feature.

Routes stay thin: they read parameters and call one function here.

The calendar does not depend on the enrolment service. Events may carry an
optional free-text `subject` label (for example "41026"), which is stored as
given and never validated against another service, so the calendar runs
standalone.
"""
from datetime import datetime

from services import database_api

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


def _decorate(event):
    """Attach the display colour for the event's type."""
    event = dict(event)
    event["color"] = EVENT_TYPES.get(event.get("event_type"), EVENT_TYPES["other"])
    return event


def _parse(value):
    return datetime.strptime(value.replace("T", " ")[:16], TIME_FORMAT)


def list_events(student_id, subject=None, start_date=None, end_date=None):
    """Events for a student, optionally filtered by subject label."""
    status_code, body = database_api.list_events(
        student_id, subject, start_date, end_date
    )
    if status_code != 200:
        return status_code, body

    events = [_decorate(event) for event in body]
    return 200, {"events": events, "count": len(events)}


def get_event(event_id):
    status_code, body = database_api.get_event(event_id)
    if status_code != 200:
        return status_code, body
    return 200, _decorate(body)


def add_event(data):
    """Create an event after validating its type."""
    event_type = data.get("event_type")
    if event_type and event_type not in EVENT_TYPES:
        return 400, {
            "error": f"Unknown event_type '{event_type}'. "
                     f"Valid types: {', '.join(sorted(EVENT_TYPES))}"
        }

    status_code, body = database_api.create_event(data)
    if status_code != 201:
        return status_code, body

    return 201, _decorate(body)


def update_event(event_id, data):
    event_type = data.get("event_type")
    if event_type and event_type not in EVENT_TYPES:
        return 400, {"error": f"Unknown event_type '{event_type}'"}

    status_code, body = database_api.update_event(event_id, data)
    if status_code != 200:
        return status_code, body
    return 200, _decorate(body)


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

    event = _decorate(moved)

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
