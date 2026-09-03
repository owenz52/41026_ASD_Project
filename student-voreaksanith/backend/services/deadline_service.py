"""Cross-service calendar features.

Two things live here:

  import_deadlines  — find assessments and exams that are not yet in the
                      calendar and offer to add them (nothing is written until
                      the student confirms)
  daily_briefing    — a short summary of today's schedule, what is due soon,
                      and the next exam

Both read from other teams' services through deadline_sources, which only ever
performs GETs against endpoints that already exist.
"""
from datetime import datetime, timedelta

import requests

from config import OLLAMA_MODEL
from services import calendar_service, database_api, deadline_sources
from services.llm_client import ask_llm
from services.prompt_loader import load_prompt, render_prompt

TIME_FORMAT = "%Y-%m-%d %H:%M"
PROMPT_DIR = "service/implementation"

# How close two events must be to count as "already in the calendar".
MATCH_WINDOW_HOURS = 36


class LLMUnavailableError(Exception):
    pass


def _parse(value):
    return datetime.strptime(str(value).replace("T", " ")[:16], TIME_FORMAT)


def _now(from_date=None):
    if from_date:
        return _parse(from_date)
    return datetime.now().replace(second=0, microsecond=0)


def _call_llm(system_prompt, user_prompt):
    try:
        return ask_llm(system_prompt, user_prompt)
    except requests.exceptions.RequestException as error:
        raise LLMUnavailableError(str(error)) from error


def _normalise_title(title):
    return "".join(ch for ch in str(title).lower() if ch.isalnum())


def _already_in_calendar(item, events):
    """Whether a deadline already has a matching calendar event.

    Matches on a normalised title plus a due time within a window, so an event
    the student typed by hand ("Assignment 2 due" at 17:00 rather than 23:59)
    is still recognised and not duplicated.
    """
    item_due = _parse(item["due"])
    item_title = _normalise_title(item["title"])

    for event in events:
        if _normalise_title(event["title"]) != item_title:
            continue
        gap = abs((_parse(event["start_time"]) - item_due).total_seconds())
        if gap <= MATCH_WINDOW_HOURS * 3600:
            return True
    return False


# --------------------------------------------------------------- feature 1

def find_missing_deadlines(student_id, from_date=None, horizon_days=60):
    """Assessments and exams that are not yet on the calendar.

    Nothing is written. The caller reviews the list and confirms.
    """
    now = _now(from_date)
    horizon_end = now + timedelta(days=int(horizon_days))

    items, sources = deadline_sources.collect_deadlines(student_id)

    status_code, body = calendar_service.list_events(student_id)
    events = body.get("events", []) if status_code == 200 else []

    missing, already, past, completed = [], [], [], []

    for item in items:
        try:
            due = _parse(item["due"])
        except ValueError:
            continue

        if due < now:
            past.append(item)
            continue
        if due > horizon_end:
            continue

        # Finished work should never be added to the calendar as a deadline.
        if str(item.get("status")).lower() in ("completed", "complete", "done"):
            completed.append(item)
            continue

        if _already_in_calendar(item, events):
            already.append(item)
            continue

        days_left = (due - now).days
        missing.append({
            **item,
            "days_until_due": days_left,
            "event_type": "exam" if item["source"] == "exam" else "deadline",
            "start_time": item["due"],
            # Exams occupy a real slot; a due date is a point in time.
            "end_time": (
                (due + timedelta(hours=2)).strftime(TIME_FORMAT)
                if item["source"] == "exam" else item["due"]
            ),
        })

    return {
        "missing": missing,
        "missing_count": len(missing),
        "already_in_calendar": len(already),
        "past_due_skipped": len(past),
        "completed_skipped": len(completed),
        "sources": sources,
        "horizon_days": int(horizon_days),
    }


def import_deadlines(student_id, items):
    """Create calendar events from deadlines the student accepted."""
    created, failed, skipped = [], [], []

    status_code, body = calendar_service.list_events(student_id)
    existing = body.get("events", []) if status_code == 200 else []

    for item in items or []:
        # Re-check at write time: the student may have added it manually
        # between previewing and confirming.
        if _already_in_calendar(item, existing):
            skipped.append(item.get("title"))
            continue

        payload = {
            "student_id": student_id,
            "subject": item.get("subject"),
            "title": item.get("title", "Deadline"),
            "event_type": item.get("event_type", "deadline"),
            "start_time": item.get("start_time") or item.get("due"),
            "end_time": item.get("end_time") or item.get("due"),
            "location": item.get("location", ""),
        }

        code, result = calendar_service.add_event(payload)
        if code == 201:
            created.append(result)
            existing.append(result)
        else:
            failed.append({
                "title": item.get("title"),
                "error": result.get("error", "unknown error"),
            })

    return {
        "created": created,
        "created_count": len(created),
        "skipped_duplicates": skipped,
        "failed": failed,
        "failed_count": len(failed),
    }


# --------------------------------------------------------------- feature 4

def _urgency(item, now):
    """Weighting per day remaining — the ranking used by the planner.

    A 40% assignment due in 5 days outranks a 10% quiz due tomorrow, which is
    the judgement students most often get wrong.
    """
    due = _parse(item["due"])
    days = max((due - now).total_seconds() / 86400.0, 0.25)
    return round(float(item.get("weighting") or 0) / days, 2)


def daily_briefing(student_id, from_date=None):
    """A short summary of today, what is due soon, and the next exam."""
    now = _now(from_date)
    today = now.strftime("%Y-%m-%d")
    week_end = now + timedelta(days=7)

    status_code, body = calendar_service.list_events(
        student_id,
        start_date=today,
        end_date=(now + timedelta(days=14)).strftime("%Y-%m-%d"),
    )
    events = body.get("events", []) if status_code == 200 else []

    todays_events = sorted(
        (e for e in events if e["start_time"].startswith(today)),
        key=lambda e: e["start_time"],
    )

    items, sources = deadline_sources.collect_deadlines(student_id)

    upcoming = []
    for item in items:
        try:
            due = _parse(item["due"])
        except ValueError:
            continue
        if due < now:
            continue
        if str(item.get("status")).lower() in ("completed", "complete"):
            continue
        upcoming.append({
            **item,
            "days_until_due": (due - now).days,
            "urgency": _urgency(item, now),
        })

    due_this_week = [i for i in upcoming if _parse(i["due"]) <= week_end]
    next_exam = next((i for i in upcoming if i["source"] == "exam"), None)
    priorities = sorted(upcoming, key=lambda i: -i["urgency"])[:3]

    facts = {
        "date": today,
        "events_today": [
            {"time": e["start_time"][11:16], "title": e["title"],
             "type": e["event_type"], "location": e.get("location") or ""}
            for e in todays_events
        ],
        "due_this_week": [
            {"title": i["title"], "due": i["due"], "weighting": i["weighting"],
             "days_until_due": i["days_until_due"]}
            for i in due_this_week
        ],
        "next_exam": (
            {"title": next_exam["title"], "when": next_exam["due"],
             "days_until": next_exam["days_until_due"]}
            if next_exam else None
        ),
        "top_priorities": [
            {"title": i["title"], "due": i["due"], "weighting": i["weighting"],
             "urgency": i["urgency"]}
            for i in priorities
        ],
        "sources": sources,
    }

    # The numbers above are computed here; the model only writes them up. If it
    # is unavailable the briefing still returns, just without the prose.
    summary, llm_error = None, None
    try:
        system_prompt = load_prompt(f"{PROMPT_DIR}/system_prompt.txt")
        user_prompt = render_prompt(
            f"{PROMPT_DIR}/briefing_task_prompt.txt",
            date=now.strftime("%A %d %B %Y"),
            events_today=_format_events(todays_events),
            due_this_week=_format_items(due_this_week),
            next_exam=(
                f"{next_exam['title']} on {next_exam['due']} "
                f"({next_exam['days_until_due']} days away)"
                if next_exam else "None scheduled."
            ),
            priorities=_format_items(priorities),
        )
        summary = _call_llm(system_prompt, user_prompt).strip()
    except LLMUnavailableError as error:
        llm_error = str(error)
        summary = _fallback_briefing(facts)
    except FileNotFoundError as error:
        llm_error = f"prompt missing: {error}"
        summary = _fallback_briefing(facts)

    return {
        "summary": summary,
        "facts": facts,
        "trace": {
            "operation": "daily_briefing",
            "llm_invoked": llm_error is None,
            "model": OLLAMA_MODEL if llm_error is None else None,
            "llm_error": llm_error,
            "reasoning": (
                "Counts, urgency scores and the priority order are computed in "
                "Python from the calendar, assessment and exam services. The "
                "model only phrases them, so the figures cannot be invented."
            ),
        },
    }


def _format_events(events):
    if not events:
        return "Nothing scheduled today."
    return "\n".join(
        f"- {e['start_time'][11:16]} {e['title']}"
        + (f" ({e['location']})" if e.get("location") else "")
        for e in events
    )


def _format_items(items):
    if not items:
        return "Nothing due."
    lines = []
    for i in items:
        weight = f", worth {i['weighting']:.0f}%" if i.get("weighting") else ""
        lines.append(
            f"- {i['title']} due {i['due']}"
            f" ({i['days_until_due']} days{weight})"
        )
    return "\n".join(lines)


def _fallback_briefing(facts):
    """Plain-text briefing used when Ollama is unavailable."""
    parts = []

    events = facts["events_today"]
    if events:
        first = events[0]
        parts.append(
            f"You have {len(events)} thing(s) on today, starting with "
            f"{first['title']} at {first['time']}."
        )
    else:
        parts.append("Nothing is scheduled in your calendar today.")

    due = facts["due_this_week"]
    if due:
        parts.append(f"{len(due)} item(s) are due within the next week.")

    top = facts["top_priorities"]
    if top:
        parts.append(
            f"Highest priority is {top[0]['title']}, due {top[0]['due']}."
        )

    if facts["next_exam"]:
        exam = facts["next_exam"]
        parts.append(f"Next exam is {exam['title']} in {exam['days_until']} days.")

    return " ".join(parts)
