"""Builds the knowledge base the RAG server retrieves from.

The corpus is drawn from two places:

  1. the project's own live data, read from the feature database services —
     exams, assignments, courses, enrolments, calendar events and notes
  2. any Markdown or text documents placed in documents/

Indexing live data rather than a fixed set of files is what makes the answers
useful: a student asking "when is my exam" is answered from the actual exam
timetable, and the citation points at the record it came from.

Each record becomes one passage written as a sentence, because BM25 matches
words rather than fields — "Exam ASD101 Final is on 2026-10-10 at 09:00"
matches "when is my exam" far better than a raw JSON blob would.

A feature service being unavailable removes its passages from the corpus and
is reported; it never prevents the index from being built.
"""
import os

import requests

from retrieval import Index

TIMEOUT = int(os.getenv("RAG_UPSTREAM_TIMEOUT", 10))

# A record from the student's own data outranks general documentation that
# happens to use the same words.
RECORD_WEIGHT = float(os.getenv("RAG_RECORD_WEIGHT", 1.6))
DOCUMENTS_DIR = os.getenv("RAG_DOCUMENTS_DIR", "documents")


def _url(name, default):
    return os.getenv(name, default).rstrip("/")


ENROLMENT = _url("ENROLMENT_DB_URL", "http://localhost:5002")
NOTEBOOK = _url("NOTEBOOK_DB_URL", "http://localhost:5004")
CALENDAR = _url("CALENDAR_DB_URL", "http://localhost:5006")
ASSESSMENT = _url("ASSESSMENT_DB_URL", "http://localhost:5008")
EXAM = _url("EXAM_DB_URL", "http://localhost:5010")


def _fetch(base, path, params=None):
    response = requests.get(f"{base}{path}", params=params, timeout=TIMEOUT)
    response.raise_for_status()
    body = response.json()

    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for key in ("events", "assignments", "exams", "courses",
                    "enrolments", "notes", "notebooks", "data"):
            if isinstance(body.get(key), list):
                return body[key]
    return []


def _clean(value, fallback=""):
    text = str(value).strip() if value not in (None, "") else ""
    return text or fallback


def build_index(student_id=None):
    """Build a fresh index. Returns (index, report)."""
    index = Index()
    report = {"sources": {}, "unavailable": []}

    def source_block(name, loader):
        try:
            count = loader()
            report["sources"][name] = count
        except Exception as error:                 # noqa: BLE001
            report["sources"][name] = 0
            report["unavailable"].append(
                {"source": name, "reason": f"{type(error).__name__}"})

    # ---------------------------------------------------------- exams
    def load_exams():
        rows = _fetch(EXAM, "/exams")
        n = 0
        for row in rows:
            if student_id and str(row.get("student_id")) != str(student_id):
                continue
            name = _clean(row.get("exam_name"), "An exam")
            date = _clean(row.get("exam_date"), "an unscheduled date")
            time_ = _clean(row.get("exam_time"), "an unscheduled time")
            status = _clean(row.get("status"), "scheduled")
            index.add(
                f"exam timetable, exam {row.get('exam_id')}",
                f"Exam: {name}. The exam {name} is scheduled on {date} "
                f"at {time_}. Its status is {status}. "
                f"This is an exam for course {row.get('course_id')}.",
                {"type": "exam", "exam_id": row.get("exam_id"),
                 "date": date, "time": time_}, weight=RECORD_WEIGHT)
            n += 1
        return n

    # ---------------------------------------------------- assignments
    def load_assignments():
        params = {"student_id": student_id} if student_id else None
        rows = _fetch(ASSESSMENT, "/assignments", params)
        n = 0
        for row in rows:
            if student_id and str(row.get("student_id")) != str(student_id):
                continue
            title = _clean(row.get("title"), "An assignment")
            due = _clean(row.get("due_date"), "no due date")
            weight = row.get("weighting")
            status = _clean(row.get("status"), "not started").replace("_", " ")
            description = _clean(row.get("description"))
            index.add(
                f"assessment tracker, assignment {row.get('assignment_id')}",
                f"Assignment: {title}. The assignment {title} is due on {due}. "
                f"It is worth {weight} percent of the subject mark. "
                f"Its status is {status}. It belongs to course "
                f"{row.get('course_id')}. {description}",
                {"type": "assignment", "due_date": due, "weighting": weight,
                 "status": status}, weight=RECORD_WEIGHT)
            n += 1
        return n

    # ------------------------------------------------ calendar events
    def load_events():
        params = {"student_id": student_id} if student_id else None
        rows = _fetch(CALENDAR, "/events", params)
        n = 0
        for row in rows:
            if student_id and str(row.get("student_id")) != str(student_id):
                continue
            title = _clean(row.get("title"), "An event")
            kind = _clean(row.get("event_type"), "event")
            start = _clean(row.get("start_time"), "an unscheduled time")
            where = _clean(row.get("location"))
            subject = _clean(row.get("subject"))
            index.add(
                f"calendar, event {row.get('event_id')}",
                f"Calendar {kind}: {title}. The {kind} {title} starts at "
                f"{start}." + (f" It is held at {where}." if where else "")
                + (f" It belongs to subject {subject}." if subject else ""),
                {"type": "event", "start_time": start, "event_type": kind},
                weight=RECORD_WEIGHT)
            n += 1
        return n

    # -------------------------------------------------------- courses
    def load_courses():
        rows = _fetch(ENROLMENT, "/courses")
        for row in rows:
            code = _clean(row.get("course_code"))
            name = _clean(row.get("course_name"), "A course")
            description = _clean(row.get("description"))
            index.add(
                f"course catalogue, {code or row.get('course_id')}",
                f"Course {code}: {name}. {description} "
                f"The course code for {name} is {code}.",
                {"type": "course", "course_code": code}, weight=RECORD_WEIGHT)
        return len(rows)

    # ----------------------------------------------------- enrolments
    def load_enrolments():
        rows = _fetch(ENROLMENT, "/enrolments")
        n = 0
        for row in rows:
            if student_id and str(row.get("student_id")) != str(student_id):
                continue
            index.add(
                f"enrolments, record {row.get('enrolment_id')}",
                f"Enrolment: student {row.get('student_id')} is "
                f"{_clean(row.get('enrolment_status'), 'enrolled')} in course "
                f"{row.get('course_id')} as of "
                f"{_clean(row.get('enrolment_date'), 'an unrecorded date')}.",
                {"type": "enrolment"}, weight=RECORD_WEIGHT)
            n += 1
        return n

    # ---------------------------------------------------------- notes
    def load_notes():
        notebooks = _fetch(NOTEBOOK, "/notebooks")
        n = 0
        for notebook in notebooks:
            nb_id = notebook.get("notebook_id")
            try:
                notes = _fetch(NOTEBOOK, f"/notebooks/{nb_id}/notes")
            except Exception:                      # noqa: BLE001
                continue
            for note in notes:
                title = _clean(note.get("note_title"), "A note")
                content = _clean(note.get("note_content"))
                index.add(
                    f"notebook {_clean(notebook.get('notebook_title'), nb_id)}, "
                    f"note {note.get('note_id')}",
                    f"Note: {title}. {content}",
                    {"type": "note", "notebook_id": nb_id}, weight=RECORD_WEIGHT)
                n += 1
        return n

    for name, loader in [("exams", load_exams),
                         ("assignments", load_assignments),
                         ("calendar_events", load_events),
                         ("courses", load_courses),
                         ("enrolments", load_enrolments),
                         ("notes", load_notes)]:
        source_block(name, loader)

    # ------------------------------------------------------ documents
    docs = 0
    if os.path.isdir(DOCUMENTS_DIR):
        for filename in sorted(os.listdir(DOCUMENTS_DIR)):
            if not filename.lower().endswith((".md", ".txt")):
                continue
            path = os.path.join(DOCUMENTS_DIR, filename)
            try:
                text = open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                continue

            # Split on blank lines so a citation points at a paragraph rather
            # than a whole file.
            for i, block in enumerate(
                    b.strip() for b in text.split("\n\n") if b.strip()):
                index.add(f"{filename}, paragraph {i + 1}", block,
                          {"type": "document", "file": filename})
                docs += 1
    report["sources"]["documents"] = docs

    index.finalise()
    report["passages"] = len(index)
    return index, report
