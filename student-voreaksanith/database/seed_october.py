"""Add October 2026 sample events to the calendar database.

Covers every event type the calendar understands (lecture, seminar, lab,
deadline, exam, revision, office_hours, other) for student 1.

Kept separate from init_db.py on purpose: init_db.py is rebuilt by the test
suite, which asserts exact event counts, so extra rows there would break it.

Idempotent: events use fixed ids (101+) and are replaced on every run.

    python database/seed_october.py
"""
import os
import sqlite3

DB = os.path.join(os.path.dirname(__file__), "data", "calendar.db")
STUDENT_ID = 1

# (subject, title, event_type, start_time, end_time, location)
OCTOBER_EVENTS = [
    # lecture
    ("41026", "ASD Lecture", "lecture", "2026-10-07 10:00", "2026-10-07 11:30", "CB11.05.300"),
    ("41026", "ASD Lecture", "lecture", "2026-10-14 10:00", "2026-10-14 11:30", "CB11.05.300"),
    ("41026", "ASD Lecture", "lecture", "2026-10-21 10:00", "2026-10-21 11:30", "CB11.05.300"),
    # seminar
    ("41026", "AI in Software Engineering Seminar", "seminar", "2026-10-08 14:00", "2026-10-08 15:30", "CB11.05.400"),
    ("41026", "Guest Seminar: Agentic Systems", "seminar", "2026-10-22 14:00", "2026-10-22 15:30", "CB11.05.400"),
    # lab
    ("41026", "ASD Tutorial", "lab", "2026-10-02 13:00", "2026-10-02 15:00", "CB11.04.200"),
    ("41026", "ASD Tutorial", "lab", "2026-10-16 13:00", "2026-10-16 15:00", "CB11.04.200"),
    ("31271", "Database Lab", "lab", "2026-10-28 11:00", "2026-10-28 13:00", "CB02.06.110"),
    # deadline
    ("41026", "Sprint 3 demo", "deadline", "2026-10-09 17:00", "2026-10-09 17:00", ""),
    ("31271", "Database Project Milestone", "deadline", "2026-10-16 23:59", "2026-10-16 23:59", ""),
    ("41026", "Assignment 3 due", "deadline", "2026-10-23 23:59", "2026-10-23 23:59", ""),
    # exam (the existing 'ASD101 Final Exam' on 10 Oct is already in the db)
    ("41026", "Quiz 3", "exam", "2026-10-14 13:00", "2026-10-14 14:00", "CB11.05.300"),
    ("31271", "Database Mid-session Exam", "exam", "2026-10-27 09:00", "2026-10-27 11:00", "CB02.06.100"),
    # revision
    ("101", "ASD101 Exam Revision", "revision", "2026-10-08 18:00", "2026-10-08 20:00", "Library"),
    ("41026", "Quiz 3 Revision", "revision", "2026-10-12 18:00", "2026-10-12 19:30", "Library"),
    ("31271", "Database Exam Revision", "revision", "2026-10-25 14:00", "2026-10-25 16:00", "Library"),
    # office_hours
    ("41026", "Tutor Consultation", "office_hours", "2026-10-06 15:00", "2026-10-06 16:00", "CB11.05.120"),
    ("31271", "Lecturer Office Hours", "office_hours", "2026-10-20 15:00", "2026-10-20 16:00", "CB02.06.210"),
    # other
    (None, "Group Project Meeting", "other", "2026-10-13 16:00", "2026-10-13 17:00", "The Underground"),
    (None, "Open Day Volunteering", "other", "2026-10-17 09:00", "2026-10-17 13:00", "UTS Tower Foyer"),
    (None, "Part-time Work Shift", "other", "2026-10-24 10:00", "2026-10-24 16:00", ""),
]

FIRST_ID = 101


def seed():
    conn = sqlite3.connect(DB)
    rows = [(FIRST_ID + i, STUDENT_ID, *event)
            for i, event in enumerate(OCTOBER_EVENTS)]
    conn.executemany(
        """INSERT OR REPLACE INTO events
           (event_id, student_id, subject, title, event_type,
            start_time, end_time, location)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
    conn.close()
    print(f"{len(rows)} October events added for student {STUDENT_ID}")


if __name__ == "__main__":
    seed()
