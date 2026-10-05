"""How the calendar reads a question, and what that changes.

Two behaviours, tested without any server so it is fast and exact:

  1. Confidence reflects how much of the question the cited record covers. It
     used to count cited sources, which is nearly always one, so nearly every
     answer read "low" whether or not it was right.

  2. A forward-looking question ("when is my assignment", "what is due first")
     is only answered from what is still ahead, and "next" keeps only the
     soonest match. Before, the shared server's word matching could answer with
     an assignment that was due last month.

"Today" is fixed, so the result never depends on the clock.
"""
import os
import sys
from datetime import date

os.environ["RAG_ENABLED"] = "1"   # this process only; CI turns RAG off for the job

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, BACKEND)

from services import rag_client, rag_documents, rag_text   # noqa: E402

results = []


def check(label, ok, detail=""):
    results.append(ok)
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  -- {detail}" if detail else ""))


TODAY = date(2026, 10, 4)

EVENTS = [
    {"event_id": 1, "title": "ASD Lecture", "event_type": "lecture", "subject": "41026",
     "start_time": "2026-09-24 10:00", "end_time": "2026-09-24 11:30", "location": "CB11.05.300"},
    {"event_id": 2, "title": "ASD Lecture", "event_type": "lecture", "subject": "41026",
     "start_time": "2026-10-07 10:00", "end_time": "2026-10-07 11:30", "location": "CB11.05.300"},
    {"event_id": 3, "title": "ASD Lecture", "event_type": "lecture", "subject": "41026",
     "start_time": "2026-10-14 10:00", "end_time": "2026-10-14 11:30", "location": "CB11.05.300"},
    {"event_id": 4, "title": "ASD Tutorial", "event_type": "lab", "subject": "41026",
     "start_time": "2026-10-08 13:00", "end_time": "2026-10-08 15:00", "location": ""},
    {"event_id": 5, "title": "Sprint 2 demo", "event_type": "deadline", "subject": "41026",
     "start_time": "2026-09-30 17:00", "end_time": "2026-09-30 17:00", "location": ""},
    {"event_id": 6, "title": "Group meeting", "event_type": "other", "subject": None,
     "start_time": "2026-10-04 09:00", "end_time": "2026-10-04 10:00", "location": "Library"},
]

ITEMS = [
    {"source": "assessment", "source_id": 1, "title": "API Integration Task", "subject": "48024",
     "due": "2026-09-16 23:59", "weighting": 20, "status": "not_started"},       # overdue
    {"source": "assessment", "source_id": 2, "title": "Architecture Report", "subject": "41026",
     "due": "2026-10-09 23:59", "weighting": 35, "status": "in_progress"},
    {"source": "assessment", "source_id": 3, "title": "Database Assignment", "subject": "31271",
     "due": "2026-10-16 23:59", "weighting": 40, "status": "not_started"},
    {"source": "assessment", "source_id": 4, "title": "Weekly Quiz 3", "subject": "41026",
     "due": "2026-10-12 23:59", "weighting": 5, "status": "completed"},          # done early
    {"source": "exam", "source_id": 1, "title": "ASD101 Final Examination", "subject": "101",
     "due": "2026-10-25 09:00", "weighting": 50.0, "status": "Uncompleted"},
    {"source": "exam", "source_id": 2, "title": "Old Quiz Exam", "subject": "101",
     "due": "2026-09-01 09:00", "weighting": 50.0, "status": "Completed"},       # long past
]

state = {"events": EVENTS, "items": ITEMS}

rag_documents.calendar_service.list_events = (
    lambda sid, *a, **k: (200, {"events": state["events"]}))
rag_documents.deadline_sources.collect_deadlines = (
    lambda sid: (state["items"], {"assessments": {"available": True, "count": 4},
                                  "exams": {"available": True, "count": 2}}))


def docs(question=None, **kw):
    return rag_documents.build_documents(1, question=question, today=TODAY, **kw)


def ids(documents):
    return {d["source_id"] for d in documents}


print("\n--- Reading a question: forward-looking, past, or neither ---")
for question, upcoming, nearest in [
    ("When is my assignment", True, False),
    ("when is my next exam", True, True),
    ("what is due first?", True, True),
    ("What are my upcoming deadlines", True, False),
    ("when was my last quiz", False, False),
    ("when did I submit the report", False, False),
    ("which assignments are overdue", False, False),
    ("what exams do I have", False, False),
    ("What is the capital of France?", False, False),
]:
    got = (rag_text.wants_upcoming(question), rag_text.wants_nearest(question))
    check(f"{question!r}", got == (upcoming, nearest),
          f"upcoming={got[0]} nearest={got[1]}")

print("\n--- Confidence: how much of the question the cited record covers ---")
lecture = rag_documents._sentence(EVENTS[1])
exam = rag_documents._assessment_sentence(ITEMS[4])
assignment = rag_documents._assessment_sentence(ITEMS[0])

for question, text, expected, why in [
    ("when is my lecture", lecture, "high", "the screenshot case that used to read low"),
    ("When is my assignment", assignment, "high", "the second screenshot case"),
    ("when is my next exam", exam, "high", "'next' is how it is asked, not what"),
    ("when are my lectures", lecture, "high", "plural matches singular"),
    ("when is my chemistry lecture", lecture, "medium", "covers lecture, not chemistry"),
    ("when is my chemistry practical report", lecture, "low", "covers nothing it asked"),
    ("what is next", lecture, "low", "no specific words to match"),
]:
    cov = rag_text.coverage(question, [text])
    got = rag_text.level(cov)
    check(f"{question!r} -> {expected}", got == expected,
          f"{why}; matched={cov['matched']} missing={cov['missing']}")

cov = rag_text.coverage("when is my chemistry lecture", [lecture])
check("the basis names what was and was not found",
      rag_text.basis(cov) ==
      "The cited record covers 1 of 2 words in your question (lecture); not found: chemistry.",
      rag_text.basis(cov))
check("the basis is honest when there is nothing to match",
      "no specific words" in rag_text.basis(rag_text.coverage("what is next", [lecture])))
check("more than one cited record is worded as such",
      "records cover" in rag_text.basis(cov, 2))

print("\n--- No question: everything is sent, as before ---")
documents, report = docs()
check("every event and item is sent", len(documents) == 12, str(len(documents)))
check("nothing is marked as filtered",
      report["upcoming_only"] is False and report["left_out"] == 0)

print("\n--- A forward-looking question leaves out what is behind you ---")
documents, report = docs("When is my assignment")
got = ids(documents)
check("the overdue assignment is not sent", "assessment:1" not in got)
check("the already-completed assignment is not sent", "assessment:4" not in got)
check("upcoming assignments are sent", {"assessment:2", "assessment:3"} <= got)
check("past events are not sent", {"calendar:1", "calendar:5"}.isdisjoint(got))
check("an event today still counts as ahead", "calendar:6" in got)
check("the long-past exam is not sent", "exam:2" not in got)
check("the report says what it left out", report["upcoming_only"] is True
      and report["left_out"] == 5, f"left_out={report['left_out']}")
check("documents sent = 7", len(documents) == 7, str(len(documents)))

print("\n--- 'Next' keeps only the soonest match ---")
documents, report = docs("when is my next lecture")
lectures = [d for d in documents if "lecture" in d["text"].lower()]
check("exactly one lecture is sent", len(lectures) == 1, str(ids(lectures)))
check("it is the soonest one still ahead", lectures[0]["source_id"] == "calendar:2",
      lectures[0]["source_id"])
check("the later lecture was dropped", "calendar:3" not in ids(documents))
check("the report records the narrowing", report["nearest_only"] is True
      and report["narrowed_to_next"] == 1, f"narrowed={report['narrowed_to_next']}")
documents, _ = docs("when is my next exam")
check("'next exam' still sends the exam", "exam:1" in ids(documents))
documents, _ = docs("when is my next assignment")
check("'next assignment' sends the soonest assignment only",
      "assessment:2" in ids(documents) and "assessment:3" not in ids(documents),
      str(sorted(i for i in ids(documents) if i.startswith("assessment"))))
documents, _ = docs("what are my upcoming assignments")
check("'upcoming' without 'next' sends the whole list",
      {"assessment:2", "assessment:3"} <= ids(documents))

print("\n--- Questions about the past, or neither, get everything ---")
documents, report = docs("when was my last lecture")
check("a past question is not narrowed", report["upcoming_only"] is False)
check("so the past lecture is available", "calendar:1" in ids(documents))
documents, report = docs("What is the capital of France?")
check("an unrelated question is left alone", len(documents) == 12
      and report["upcoming_only"] is False)

print("\n--- When nothing is ahead ---")
state["events"] = []
state["items"] = [ITEMS[5]]   # only a long-past exam
documents, report = docs("when is my exam")
check("no documents are sent", documents == [], str(len(documents)))
check("the report says why", report["upcoming_only"] and report["left_out"] == 1)
answer = rag_client.ask_for_student("when is my exam", 1)
check("the student is told nothing is upcoming, not that records are missing",
      answer["grounded"] is False and "nothing upcoming" in answer.get("reason", ""),
      answer.get("reason"))
state["events"], state["items"] = EVENTS, ITEMS

print("\n--- What is sent still satisfies the shared server's rules ---")
for question in (None, "when is my next lecture", "When is my assignment"):
    documents, _ = docs(question)
    chunk_ids = [d["chunk_id"] for d in documents]
    check(f"valid for {question!r}",
          len(documents) <= 100
          and len(chunk_ids) == len(set(chunk_ids))
          and all(d["feature"] == "calendar" and d["student_id"] == 1
                  and 0 < len(d["text"]) <= 2000 for d in documents),
          f"{len(documents)} documents")

documents, report = docs(limit=3)
check("the cap is respected and reported", len(documents) == 3 and report["truncated"] is True)

print(f"\n{'=' * 58}\n  {sum(results)}/{len(results)} checks passed\n{'=' * 58}")
sys.exit(0 if all(results) else 1)
