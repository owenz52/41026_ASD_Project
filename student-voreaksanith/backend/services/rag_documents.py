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
from config import RAG_FEATURE, RAG_MAX_CHARS, RAG_MAX_DOCUMENTS
from services import calendar_service, deadline_sources

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


def build_documents(student_id, limit=None):
    """Calendar documents for one student, ready to send to the RAG server.

    Returns (documents, report). The report records how many events were read
    and whether any were dropped, so the caller can say what was searched.
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

    # Deadlines and exams first, so that when the cap truncates the list the
    # most-asked-about events are the ones that survive.
    def priority(event):
        order = {"deadline": 0, "exam": 0, "revision": 1}
        return (order.get(event.get("event_type"), 2),
                event.get("start_time") or "")

    documents = []
    for event in sorted(events, key=priority):
        text = _sentence(event)
        if not text.strip():
            continue

        documents.append({
            "chunk_id": f"calendar-event-{event.get('event_id')}",
            "source_id": f"calendar:{event.get('event_id')}",
            "text": text,
            "feature": RAG_FEATURE,
            "student_id": sid,
            "authority_tier": AUTHORITY_TIER,
        })

        if len(documents) >= limit:
            break

    calendar_count = len(documents)

    # Assessments and exams, read from the services that own them. A failure
    # there reduces what can be answered; it never fails the request.
    external = []
    sources = {}
    try:
        external, sources = deadline_sources.collect_deadlines(sid)
    except Exception:                              # noqa: BLE001
        sources = {}

    seen = {d["chunk_id"] for d in documents}

    for item in external:
        if len(documents) >= limit:
            break

        chunk_id = f"{item.get('source')}-{item.get('source_id')}"
        if chunk_id in seen:
            continue
        seen.add(chunk_id)

        text = _assessment_sentence(item)
        if not text.strip():
            continue

        documents.append({
            "chunk_id": chunk_id,
            "source_id": f"{item.get('source')}:{item.get('source_id')}",
            "text": text,
            "feature": RAG_FEATURE,
            "student_id": sid,
            "authority_tier": AUTHORITY_TIER,
        })

    return documents, {
        "events": len(events),
        "calendar_documents": calendar_count,
        "assessment_documents": len(documents) - calendar_count,
        "documents": len(documents),
        "truncated": (len(events) + len(external)) > len(documents),
        "sources": sources,
    }
