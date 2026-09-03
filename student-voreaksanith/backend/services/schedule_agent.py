
from datetime import datetime, timedelta

import requests

from config import (
    AGENT_HORIZON_DAYS,
    AGENT_MAX_CANDIDATE_SLOTS,
    AGENT_MAX_SUGGESTIONS,
    AGENT_SESSION_MINUTES,
    AGENT_STUDY_END_HOUR,
    AGENT_STUDY_START_HOUR,
    OLLAMA_MODEL,
)
from services import calendar_service, deadline_sources
from services.llm_client import ask_llm
from services.prompt_loader import load_prompt, render_prompt

TIME_FORMAT = "%Y-%m-%d %H:%M"
PROMPT_DIR = "service/implementation"

# Event types worth preparing for.
TARGET_TYPES = {"deadline", "exam"}

# Slots are generated on this grid, in minutes.
SLOT_STEP_MINUTES = 30


class LLMUnavailableError(Exception):
    pass


def _parse(value):
    return datetime.strptime(str(value).replace("T", " ")[:16], TIME_FORMAT)


def _norm(title):
    return "".join(ch for ch in str(title).lower() if ch.isalnum())


def _call_llm(system_prompt, user_prompt):
    try:
        return ask_llm(system_prompt, user_prompt)
    except requests.exceptions.RequestException as error:
        raise LLMUnavailableError(str(error)) from error


def _overlaps(start, end, busy):
    return any(start < b_end and end > b_start for b_start, b_end in busy)


def _build_free_slots(from_dt, until_dt, busy, session_minutes, limit):
    """Every free session-length slot inside study hours before a deadline.

    Deterministic: the model chooses from this list, it does not produce times.
    """
    slots = []
    duration = timedelta(minutes=session_minutes)
    step = timedelta(minutes=SLOT_STEP_MINUTES)

    day = from_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    last_day = until_dt.replace(hour=0, minute=0, second=0, microsecond=0)

    while day <= last_day and len(slots) < limit:
        cursor = day.replace(hour=AGENT_STUDY_START_HOUR, minute=0)
        day_end = day.replace(hour=AGENT_STUDY_END_HOUR, minute=0)

        while cursor + duration <= day_end:
            start, end = cursor, cursor + duration

            # Never suggest a slot in the past or after the deadline itself.
            if start >= from_dt and end <= until_dt and not _overlaps(start, end, busy):
                slots.append({"start": start, "end": end})
                if len(slots) >= limit:
                    break
                # One slot per day per pass keeps suggestions spread out and
                # keeps the prompt short.
                break

            cursor += step

        day += timedelta(days=1)

    return slots


def _format_deadlines(targets):
    lines = []
    for target in targets:
        subject = target.get("subject") or "general"
        weight = target.get("weighting") or 0
        detail = f", worth {weight:.0f}%" if weight else ""
        lines.append(
            f"- {target['title']} ({subject}), due {target['start_time']}{detail}"
        )
    return "\n".join(lines)


def _format_slots(slots):
    return "\n".join(
        f"- {slot['id']}: {slot['start'].strftime('%A %d %B, %H:%M')} "
        f"to {slot['end'].strftime('%H:%M')}"
        for slot in slots
    )


def _parse_llm_choices(output, valid_ids):
    """Parse 'SLOT_ID | reason' lines, separating valid ids from invented ones."""
    chosen, hallucinated = [], []

    for line in (output or "").splitlines():
        line = line.strip().strip("-*\t ")
        if not line:
            continue

        if "|" in line:
            slot_id, _, reason = line.partition("|")
        else:
            slot_id, reason = line.split()[0] if line.split() else "", ""

        slot_id = slot_id.strip().upper()
        reason = reason.strip()

        if not slot_id:
            continue
        if slot_id in valid_ids:
            if slot_id not in [c["slot_id"] for c in chosen]:
                chosen.append({"slot_id": slot_id, "reason": reason})
        else:
            hallucinated.append(slot_id)

    return chosen, hallucinated


def _fallback_choices(slots, targets, max_suggestions):
    """Deterministic slot picking, used when the model fails or hallucinates.

    Spreads sessions across the earliest available days so the student gets
    something sensible even with no LLM at all.
    """
    chosen = []
    for slot in slots[:max_suggestions]:
        target = slot["target"]
        days_before = (_parse(target["start_time"]) - slot["start"]).days
        chosen.append({
            "slot_id": slot["id"],
            "reason": (
                f"Free {slot['start'].strftime('%A')} — "
                f"{days_before} day(s) before {target['title']}."
            ),
        })
    return chosen


def suggest_schedule(student_id, from_date=None, horizon_days=None):
    """Suggest study sessions for upcoming deadlines and exams.

    Returns suggestions plus a full reasoning trace. Nothing is written to the
    calendar — the student reviews the suggestions and applies them separately.
    """
    horizon_days = int(horizon_days or AGENT_HORIZON_DAYS)
    session_minutes = AGENT_SESSION_MINUTES
    max_suggestions = AGENT_MAX_SUGGESTIONS

    now = _parse(from_date) if from_date else datetime.now().replace(second=0, microsecond=0)
    horizon_end = now + timedelta(days=horizon_days)

    trace = {"operation": "suggest_schedule", "student_id": student_id}

    # ---------------------------------------------------------------- PLAN
    status_code, body = calendar_service.list_events(
        student_id,
        start_date=now.strftime("%Y-%m-%d"),
        end_date=horizon_end.strftime("%Y-%m-%d"),
    )
    if status_code != 200:
        raise RuntimeError(body.get("error", "could not load calendar"))

    events = body["events"]

    # Targets are deadlines/exams already on the calendar, plus anything the
    # assessment and exam services know about that is not on it yet. Pulling
    # both means the planner still works before a student imports deadlines.
    targets = [
        {**e, "weighting": 0.0, "origin": "calendar"}
        for e in events
        if e["event_type"] in TARGET_TYPES and _parse(e["start_time"]) > now
    ]

    external, source_status = deadline_sources.collect_deadlines(student_id)
    known = {_norm(t["title"]) for t in targets}
    for item in external:
        if _norm(item["title"]) in known:
            # Same item, already on the calendar: keep the calendar copy but
            # take the weighting, which the calendar does not store.
            for target in targets:
                if _norm(target["title"]) == _norm(item["title"]):
                    target["weighting"] = item.get("weighting", 0.0)
            continue
        try:
            due = _parse(item["due"])
        except ValueError:
            continue
        if due <= now:
            continue
        if str(item.get("status")).lower() in ("completed", "complete"):
            continue
        targets.append({
            "event_id": None,
            "title": item["title"],
            "subject": item.get("subject"),
            "event_type": "exam" if item["source"] == "exam" else "deadline",
            "start_time": item["due"],
            "end_time": item["due"],
            "weighting": item.get("weighting", 0.0),
            "origin": item["source"],
        })

    # Rank by weighting per day remaining, so a large assignment a week out
    # beats a small quiz tomorrow. Ties fall back to the earlier due date.
    for target in targets:
        days = max((_parse(target["start_time"]) - now).total_seconds() / 86400.0, 0.25)
        target["urgency"] = round(float(target.get("weighting") or 0) / days, 2)

    targets.sort(key=lambda t: (-t["urgency"], t["start_time"]))
    busy = [(_parse(e["start_time"]), _parse(e["end_time"])) for e in events]

    # Build candidate slots per target, then interleave so the prompt is not
    # dominated by whichever deadline happens to be first.
    # Build candidate slots per target. Times already claimed by an earlier
    # target are treated as busy, otherwise every deadline is offered the same
    # first free gap and the student ends up with overlapping revision sessions.
    per_target = max(1, AGENT_MAX_CANDIDATE_SLOTS // max(1, len(targets)))
    claimed = list(busy)
    candidates = []
    for target in targets:
        target_slots = _build_free_slots(
            now, _parse(target["start_time"]), claimed, session_minutes, per_target
        )
        for slot in target_slots:
            slot["target"] = target
            candidates.append(slot)
            claimed.append((slot["start"], slot["end"]))

    candidates.sort(key=lambda s: s["start"])
    candidates = candidates[:AGENT_MAX_CANDIDATE_SLOTS]
    for index, slot in enumerate(candidates, start=1):
        slot["id"] = f"S{index}"

    trace["plan"] = {
        "horizon_days": horizon_days,
        "events_in_horizon": len(events),
        "deadlines_found": [
            {"title": t["title"], "due": t["start_time"], "type": t["event_type"]}
            for t in targets
        ],
        "busy_blocks": len(busy),
        "study_hours": f"{AGENT_STUDY_START_HOUR:02d}:00-{AGENT_STUDY_END_HOUR:02d}:00",
        "session_minutes": session_minutes,
        "candidate_slots_found": len(candidates),
        "deadline_sources": source_status,
        "ranked_by": "weighting per day remaining",
        "ranking": [
            {"title": t["title"], "weighting": t.get("weighting"),
             "urgency": t.get("urgency"), "origin": t.get("origin")}
            for t in targets
        ],
        "reasoning": (
            f"Loaded {len(events)} events in the next {horizon_days} days, found "
            f"{len(targets)} deadline/exam item(s), then computed "
            f"{session_minutes}-minute gaps inside study hours that do not "
            f"overlap any existing event and fall before each deadline."
        ),
    }

    # Nothing to do — return early rather than calling the model for no reason.
    if not targets or not candidates:
        reason = "No upcoming deadlines or exams in the horizon." if not targets \
            else "No free study slots available before the upcoming deadlines."
        trace["act"] = {"llm_invoked": False, "model": None, "prompt_files": []}
        trace["observe"] = {"suggestions_returned": 0, "hallucinated_slot_ids": [],
                            "hallucination_detected": False}
        trace["adapt"] = {"action": "none", "reasoning": reason}
        return {"suggestions": [], "trace": trace}

    # ----------------------------------------------------------------- ACT
    # A missing prompt file must not take the whole request down: fall back to
    # deterministic slot selection and say so, rather than returning a 500.
    llm_failed = None
    output = ""
    system_prompt = context_prompt = task_prompt = None

    try:
        system_prompt = load_prompt(f"{PROMPT_DIR}/system_prompt.txt")
        context_prompt = load_prompt(f"{PROMPT_DIR}/context_prompt.txt")
        task_prompt = render_prompt(
            f"{PROMPT_DIR}/suggest_task_prompt.txt",
            deadline_count=len(targets),
            max_suggestions=max_suggestions,
            deadlines=_format_deadlines(targets),
            slots=_format_slots(candidates),
        )
    except (FileNotFoundError, OSError) as error:
        llm_failed = f"prompt file unavailable: {error}"

    if llm_failed is None:
        try:
            output = _call_llm(system_prompt, f"{task_prompt}\n\n{context_prompt}")
        except LLMUnavailableError as error:
            llm_failed = str(error)

    trace["act"] = {
        "llm_invoked": llm_failed is None,
        "model": OLLAMA_MODEL if llm_failed is None else None,
        "llm_error": llm_failed,
        "candidate_slot_ids_sent": [slot["id"] for slot in candidates],
        "prompt_files": [
            f"{PROMPT_DIR}/system_prompt.txt",
            f"{PROMPT_DIR}/suggest_task_prompt.txt",
            f"{PROMPT_DIR}/context_prompt.txt",
        ],
    }

    # ------------------------------------------------------------- OBSERVE
    valid_ids = {slot["id"] for slot in candidates}
    chosen, hallucinated = _parse_llm_choices(output, valid_ids)
    over_limit = len(chosen) > max_suggestions

    trace["observe"] = {
        "llm_returned_slot_ids": [c["slot_id"] for c in chosen] + hallucinated,
        "hallucinated_slot_ids": hallucinated,
        "hallucination_detected": bool(hallucinated),
        "over_max_suggestions": over_limit,
        "suggestions_returned": len(chosen),
    }

    # --------------------------------------------------------------- ADAPT
    retry_count = 0

    if llm_failed:
        chosen = _fallback_choices(candidates, targets, max_suggestions)
        adapt_action = "fallback_no_llm"
        adapt_reasoning = (
            f"AI step skipped ({llm_failed}); used deterministic "
            "earliest-free-slot selection so the student still gets a usable "
            "schedule."
        )
    elif not chosen or hallucinated:
        # One stricter retry before giving up on the model, mirroring the
        # summarise retry behaviour in the notebook feature.
        try:
            retry_prompt = render_prompt(
                f"{PROMPT_DIR}/suggest_retry_prompt.txt",
                max_suggestions=max_suggestions,
                deadlines=_format_deadlines(targets),
                slots=_format_slots(candidates),
            )
            retry_output = _call_llm(system_prompt, f"{retry_prompt}\n\n{context_prompt}")
            retry_count = 1
            chosen, hallucinated = _parse_llm_choices(retry_output, valid_ids)
        except LLMUnavailableError:
            chosen = []

        if chosen and not hallucinated:
            adapt_action = "retried_with_stricter_prompt"
            adapt_reasoning = (
                "First response was empty or referenced unknown slots; a "
                "stricter retry returned valid slot ids."
            )
        else:
            chosen = _fallback_choices(candidates, targets, max_suggestions)
            adapt_action = "fallback_earliest_free_slots"
            adapt_reasoning = (
                "Model output still referenced slots outside the candidate "
                "list; discarded it and fell back to deterministic selection."
            )
    elif over_limit:
        chosen = chosen[:max_suggestions]
        adapt_action = "truncated_to_max_suggestions"
        adapt_reasoning = (
            f"Model returned more than {max_suggestions} slots; capped in code "
            "rather than trusting it to self-limit."
        )
    else:
        adapt_action = "none"
        adapt_reasoning = "All returned slot ids were valid; accepted the model's choices."

    trace["adapt"] = {
        "action": adapt_action,
        "retry_count": retry_count,
        "reasoning": adapt_reasoning,
    }

    # Turn chosen slot ids back into concrete, ready-to-create events.
    slots_by_id = {slot["id"]: slot for slot in candidates}
    suggestions = []
    taken = []
    skipped_overlapping = []

    for choice in chosen:
        if len(suggestions) >= max_suggestions:
            break

        slot = slots_by_id[choice["slot_id"]]

        # Final guard: the model could still choose two slots that overlap each
        # other, which would double-book the student.
        if _overlaps(slot["start"], slot["end"], taken):
            skipped_overlapping.append(slot["id"])
            continue

        target = slot["target"]
        subject = f"{target['subject']} " if target.get("subject") else ""
        suggestions.append({
            "slot_id": slot["id"],
            "title": f"Revision — {subject}{target['title']}".strip(),
            "event_type": "revision",
            "subject": target.get("subject"),
            "start_time": slot["start"].strftime(TIME_FORMAT),
            "end_time": slot["end"].strftime(TIME_FORMAT),
            "location": "",
            "prepares_for": {
                "event_id": target.get("event_id"),
                "title": target["title"],
                "due": target["start_time"],
            },
            "reason": choice["reason"] or "Free slot before this deadline.",
        })
        taken.append((slot["start"], slot["end"]))

    if skipped_overlapping:
        trace["observe"]["skipped_overlapping_slot_ids"] = skipped_overlapping

    trace["observe"]["suggestions_returned"] = len(suggestions)
    return {"suggestions": suggestions, "trace": trace}


def apply_suggestions(student_id, suggestions):
    """Create calendar events from suggestions the student accepted.

    Suggestions are never written automatically — this runs only when the
    student explicitly confirms them.
    """
    created, failed = [], []

    for suggestion in suggestions or []:
        payload = {
            "student_id": student_id,
            "subject": suggestion.get("subject"),
            "title": suggestion.get("title", "Revision"),
            "event_type": suggestion.get("event_type", "revision"),
            "start_time": suggestion.get("start_time"),
            "end_time": suggestion.get("end_time"),
            "location": suggestion.get("location", ""),
        }
        status_code, body = calendar_service.add_event(payload)
        if status_code == 201:
            created.append(body)
        else:
            failed.append({
                "suggestion": suggestion.get("title"),
                "error": body.get("error", "unknown error"),
            })

    return {
        "created": created,
        "failed": failed,
        "created_count": len(created),
        "failed_count": len(failed),
    }
