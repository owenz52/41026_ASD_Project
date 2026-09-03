import os
import sqlite3

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DATABASE_NAME = os.path.join(DATA_DIR, "calendar.db")

os.makedirs(DATA_DIR, exist_ok=True)


EVENTS = [
    
    (1, 1, "41026", "ASD Lecture", "lecture", "2026-09-02 10:00", "2026-09-02 11:30", "CB11.05.300"),
    (2, 1, "41026", "ASD Tutorial", "lab", "2026-09-04 13:00", "2026-09-04 15:00", "CB11.04.200"),
    (3, 1, "41026", "Sprint 2 demo", "deadline", "2026-09-11 17:00", "2026-09-11 17:00", ""),
    (4, 1, "41026", "ASD Lecture", "lecture", "2026-09-09 10:00", "2026-09-09 11:30", "CB11.05.300"),
    (5, 1, "41026", "Agent AI reading", "revision", "2026-09-14 18:00", "2026-09-14 19:30", "Library"),
    (6, 1, "41026", "Quiz 2", "exam", "2026-09-16 09:00", "2026-09-16 10:00", "CB11.05.300"),
    (7, 1, "41026", "Assignment 2 due", "deadline", "2026-09-25 23:59", "2026-09-25 23:59", ""),
    (8, 1, None, "Career fair", "other", "2026-09-18 12:00", "2026-09-18 14:00", "The Underground"),
    (9, 2, "31271", "Database Fundamentals Lecture", "lecture", "2026-09-03 16:00", "2026-09-03 18:00", "CB02.06.100"),
    (10, 2, "31271", "ER modelling quiz", "exam", "2026-09-16 09:00", "2026-09-16 10:00", "CB02.06.100"),
]


def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.execute("PRAGMA foreign_keys = ON")

    # Dropped and recreated rather than CREATE TABLE IF NOT EXISTS: a database
    # left over from an earlier schema would otherwise survive and every insert
    # would fail on the missing column. This runs at build/seed time only.
    conn.execute("DROP TABLE IF EXISTS events")

    conn.execute(
        """
        CREATE TABLE events (
            event_id    INTEGER PRIMARY KEY,
            student_id  INTEGER NOT NULL,
            subject     TEXT,
            title       TEXT NOT NULL,
            event_type  TEXT NOT NULL,
            start_time  TEXT NOT NULL,
            end_time    TEXT NOT NULL,
            location    TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_student ON events (student_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_start ON events (start_time)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_subject ON events (subject)"
    )

    conn.execute("DELETE FROM events")
    conn.executemany(
        """
        INSERT INTO events (
            event_id, student_id, subject, title,
            event_type, start_time, end_time, location
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        EVENTS,
    )

    conn.commit()
    conn.close()

    print("Calendar database initialised.")
    print(f"{len(EVENTS)} events added")
    print("Database:", DATABASE_NAME)


if __name__ == "__main__":
    init_db()
