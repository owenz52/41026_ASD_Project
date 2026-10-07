"""Builds the documents the calendar sends to the shared RAG server.

The shared server is stateless: it holds no index of its own, so the calling
feature supplies the passages to search. This module builds those chunks.

Three sources are indexed, not just the calendar's own events. A student
looking at a calendar asks "when is my next exam" and "what is due first",
and those answers live in the Exam and Assessment Tracker services. The
calendar already reads both for its deadline import, so including them here
means a question gets answered from the authoritative record rather than
returning insufficient context because the item was never imported.

Each chunk's source_id names where the fact came from — calendar:12,
assessment:4, exam:1 — so a citation points at the owning service.

The question shapes what is sent. The shared server ranks by shared words and
knows nothing about dates, so asked "when is my assignment" it can answer with
one that was due last month. Two rules fix that before the server sees anything:

  forward-looking   a question about what is due, next or upcoming is answered
                    only from items that are still ahead and not completed
  "next"            when it wants the single nearest match, only the soonest of
                    the best-matching records is sent, so the server cannot
                    choose a later one

A question about the past ("when was my last quiz"), or one that is neither,
gets everything, as before.

The server validates strictly, and rejects the whole request if any document
is wrong. Its rules, from ai-services/rag-server/rag_pipeline.py:

  - at most 100 documents
  - chunk_id, source_id and text must be non-empty strings
  - every document's feature must equal the request's feature
  - every document's student_id must equal the request's student_id
  - text at most 2000 characters
  - chunk_id must be unique within the request

Each event becomes one chunk written as a sentence rather than as raw fields,
because retrieval matches words: "Assignment 2 due is a deadline starting at
2026-09-25 23:59" matches "when is my assignment due" far better than a JSON
object would.
"""
from datetime import date, datetime, time as dtime

from config import RAG_FEATURE, RAG_MAX_CHARS, RAG_MAX_DOCUMENTS
from services import calendar_service, deadline_sources, rag_text

# The server reads authority_tier as metadata; tier_1 marks a record from the
# student's own data rather than general material.
AUTHORITY_TIER = "tier_1"


def _sentence(event):
    """One event as a sentence, for word-based retrieval."""
    title = (event.get("title") or "Untitled event").strip()
    kind = (event.get("event_type") or "event").replace("_", " ")
    start = (event.get("start_time") or "").strip()
    end = (event.get("end_time") or "").strip()
    where = (event.get("location") or "").strip()
    subject = (event.get("subject") or "").strip()

    parts = [f"Calendar {kind}: {title}."]

    if start:
        parts.append(f"The {kind} {title} starts at {start}.")
    if end and end != start:
        parts.append(f"It finishes at {end}.")
    if where:
        parts.append(f"It is held at {where}.")
    if subject:
        parts.append(f"It belongs to subject {subject}.")

    if kind in ("deadline", "exam"):
        parts.append(f"{title} is due at {start}." if kind == "deadline"
                     else f"The exam {title} is held at {start}.")

    return " ".join(parts)[:RAG_MAX_CHARS]


def _assessment_sentence(item):
    """One assessment or exam as a sentence, for word-based retrieval."""
    title = (item.get("title") or "Untitled").strip()
    due = (item.get("due") or "").strip()
    weighting = item.get("weighting")
    status = str(item.get("status") or "").replace("_", " ").strip()

    if item.get("source") == "exam":
        parts = [f"Exam: {title}.",
                 f"The exam {title} is held at {due}." if due else ""]
    else:
        parts = [f"Assignment: {title}.",
                 f"The assignment {title} is due at {due}." if due else ""]
        if weighting:
            parts.append(f"It is worth {weighting:.0f} percent of the subject mark.")

    if status:
        parts.append(f"Its status is {status}.")
    if item.get("subject"):
        parts.append(f"It belongs to subject {item['subject']}.")

    return " ".join(p for p in parts if p)[:RAG_MAX_CHARS]


COMPLETED = ("completed", "complete", "done")


def _when(value):
    """A timestamp as a datetime, or None if it cannot be read."""
    try:
        return datetime.strptime(str(value).replace("T", " ")[:16], "%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return None


def build_documents(student_id, limit=None, question=None, today=None):
    """Calendar documents for one student, ready to send to the RAG server.

    Returns (documents, report). The report records how many events were read,
    how the question narrowed them, and whether the cap dropped any, so the
    caller can say what was searched.

    question is optional. Without one, every item is sent.
    """
    limit = min(int(limit or RAG_MAX_DOCUMENTS), RAG_MAX_DOCUMENTS)

    status_code, body = calendar_service.list_events(student_id)
    if status_code != 200:
        return [], {"events": 0, "documents": 0,
                    "error": body.get("error", "could not read the calendar")}

    events = body.get("events", [])

    # The student_id must match the request exactly and be a positive integer,
    # so it is coerced once here rather than trusted from each row.
    try:
        sid = int(student_id)
    except (TypeError, ValueError):
        return [], {"events": len(events), "documents": 0,
                    "error": "student_id must be an integer"}

    if sid <= 0:
        return [], {"events": len(events), "documents": 0,
                    "error": "student_id must be positive"}

    upcoming = bool(question) and rag_text.wants_upcoming(question)
    nearest = upcoming and rag_text.wants_nearest(question)
    cutoff = datetime.combine(today or date.today(), dtime.min)
    left_out = 0

    def still_ahead(when, completed=False):
        """Whether an item belongs in a forward-looking answer."""
        if not upcoming:
            return True
        if completed:
            return False
        # An item whose time cannot be read cannot be shown to be in the past.
        return when is None or when >= cutoff

    def make(chunk_id, source_id, text):
        return {
            "chunk_id": chunk_id,
            "source_id": source_id,
            "text": text,
            "feature": RAG_FEATURE,
            "student_id": sid,
            "authority_tier": AUTHORITY_TIER,
        }

    # Deadlines and exams first, so that when the cap truncates the list the
    # most-asked-about events are the ones that survive.
    def priority(event):
        order = {"deadline": 0, "exam": 0, "revision": 1}
        return (order.get(event.get("event_type"), 2),
                event.get("start_time") or "")

    entries = []           # (document, when) in the order they will be sent
    capped = False

    for event in sorted(events, key=priority):
        when = _when(event.get("start_time"))
        if not still_ahead(when):
            left_out += 1
            continue

        text = _sentence(event)
        if not text.strip():
            continue

        if len(entries) >= limit:
            capped = True
            break

        entries.append((make(f"calendar-event-{event.get('event_id')}",
                             f"calendar:{event.get('event_id')}", text), when))

    # Assessments and exams, read from the services that own them. A failure
    # there reduces what can be answered; it never fails the request.
    external = []
    sources = {}
    try:
        external, sources = deadline_sources.collect_deadlines(sid)
    except Exception:                              # noqa: BLE001
        sources = {}

    seen = {doc["chunk_id"] for doc, _ in entries}

    for item in external:
        chunk_id = f"{item.get('source')}-{item.get('source_id')}"
        if chunk_id in seen:
            continue

        when = _when(item.get("due"))
        completed = str(item.get("status") or "").lower() in COMPLETED
        if not still_ahead(when, completed):
            left_out += 1
            continue

        text = _assessment_sentence(item)
        if not text.strip():
            continue

        if len(entries) >= limit:
            capped = True
            break

        seen.add(chunk_id)
        entries.append((make(chunk_id, f"{item.get('source')}:{item.get('source_id')}",
                             text), when))

    # "Next": among the records that match the question best, keep only the
    # soonest. The shared server ranks equal matches by a hash distance, which
    # has nothing to do with dates, so left alone it would pick any of them.
    narrowed = 0
    if nearest:
        terms = {stem for stem, _ in rag_text.question_terms(question)}

        if terms:
            scored = [(len(terms & rag_text.word_stems(doc["text"])), when, doc)
                      for doc, when in entries]
            best = max(score for score, _, _ in scored)

            if best > 0:
                dated = [when for score, when, _ in scored
                         if score == best and when is not None]

                if dated:
                    soonest = min(dated)
                    kept = [(doc, when) for score, when, doc in scored
                            if not (score == best and when is not None
                                    and when != soonest)]
                    narrowed = len(entries) - len(kept)
                    entries = kept

    documents = [doc for doc, _ in entries]
    from_calendar = sum(1 for d in documents if d["source_id"].startswith("calendar:"))

    return documents, {
        "events": len(events),
        "calendar_documents": from_calendar,
        "assessment_documents": len(documents) - from_calendar,
        "documents": len(documents),
        "truncated": capped,
        "upcoming_only": upcoming,
        "nearest_only": nearest,
        "left_out": left_out,
        "narrowed_to_next": narrowed,
        "sources": sources,
    }
