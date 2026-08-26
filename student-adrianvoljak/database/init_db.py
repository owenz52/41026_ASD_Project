import sqlite3
from pathlib import Path


DATABASE_PATH = Path(__file__).parent / "assessment_tracker.db"


def create_database():
    connection = sqlite3.connect(DATABASE_PATH)
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            due_date TEXT NOT NULL,
            weighting REAL,
            status TEXT NOT NULL DEFAULT 'not_started',
            completion_date TEXT,
            created_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)

    existing_count = cursor.execute(
        "SELECT COUNT(*) FROM assignments"
    ).fetchone()[0]
    
    #Creates sample data to test
    if existing_count == 0:
        cursor.executemany("""
            INSERT INTO assignments (
                student_id,
                course_id,
                title,
                description,
                due_date,
                weighting,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                1,
                41026,
                "Software Architecture Report",
                "Complete the software architecture report.",
                "2026-09-05",
                35,
                "in_progress"
            ),
            (
                1,
                31271,
                "Database Assignment",
                "Design and implement the required database solution.",
                "2026-09-12",
                25,
                "not_started"
            ),
            (
                1,
                48024,
                "Web Development Project",
                "Complete the frontend and backend implementation for the project.",
                "2026-09-18",
                40,
                "not_started"
            ),
            (
                1,
                41026,
                "Weekly Quiz",
                "Complete the weekly module quiz.",
                "2026-08-30",
                10,
                "completed"
            )
        ])

    connection.commit()
    connection.close()

if __name__ == "__main__":
    create_database()