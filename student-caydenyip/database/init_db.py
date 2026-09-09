import os
import sqlite3


DATA_DIR = "/app/data"
DATABASE_NAME = os.path.join(
    DATA_DIR,
    "exam.db"
)

os.makedirs(
    DATA_DIR,
    exist_ok=True
)


conn = sqlite3.connect(
    DATABASE_NAME
)

# Enable foreign key enforcement in SQLite
conn.execute("PRAGMA foreign_keys = ON")

cursor = conn.cursor()


# ==================================================
# COURSE EXAMS TABLE
# ==================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS course_exams (
    course_exam_id INTEGER PRIMARY KEY,
    course_id INTEGER NOT NULL,
    exam_name TEXT NOT NULL,
    exam_date DATE NOT NULL,
    exam_time TIME NOT NULL
)
""")


# ==================================================
# STUDENT EXAMS TABLE
# ==================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS student_exams (
    exam_id INTEGER PRIMARY KEY,
    course_exam_id INTEGER,
    course_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    exam_name TEXT NOT NULL,
    exam_date DATE NOT NULL,
    exam_time TIME NOT NULL,
    status TEXT NOT NULL,
    is_deleted INTEGER NOT NULL DEFAULT 0,

    FOREIGN KEY (course_exam_id)
        REFERENCES course_exams(course_exam_id)
)
""")


# ==================================================
# MIGRATE EXISTING DATABASE
#
# If student_exams already existed before
# course_exam_id was added, add the column.
# ==================================================

columns = cursor.execute(
    """
    PRAGMA table_info(student_exams)
    """
).fetchall()


column_names = [
    column[1]
    for column in columns
]


if "course_exam_id" not in column_names:

    cursor.execute(
        """
        ALTER TABLE student_exams
        ADD COLUMN course_exam_id INTEGER
        """
    )


if "is_deleted" not in column_names:

    cursor.execute(
        """
        ALTER TABLE student_exams
        ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0
        """
    )


# ==================================================
# CLEAR EXISTING DATA
#
# WARNING:
# This resets the database every time this script
# runs.
# ==================================================

cursor.execute(
    "DELETE FROM student_exams"
)

cursor.execute(
    "DELETE FROM course_exams"
)


# ==================================================
# COURSE EXAM TEMPLATES
# ==================================================

course_exams = [

    (1, 1, "41026 Final Exam", "2026-11-10", "09:00"),
    (2, 2, "48024 Final Exam", "2026-11-12", "13:00"),
    (3, 3, "31271 Final Exam", "2026-11-18", "10:00"),
    (4, 4, "12345 Final Exam", "2026-11-20", "09:00"),
    (5, 5, "23456 Final Exam", "2026-11-23", "13:00"),
    (6, 6, "34567 Final Exam", "2026-11-25", "10:00"),
    (7, 7, "45678 Final Exam", "2026-11-27", "09:00"),
    (8, 8, "56789 Final Exam", "2026-11-30", "13:00"),
    (9, 9, "67890 Final Exam", "2026-12-02", "10:00"),
    (10, 10, "78901 Final Exam", "2026-12-04", "09:00"),

    (11, 1, "41026 Mid-Semester Exam", "2026-09-15", "10:00"),
    (12, 2, "48024 Mid-Semester Exam", "2026-09-17", "13:00"),
    (13, 3, "31271 Mid-Semester Exam", "2026-09-22", "09:00"),
    (14, 4, "12345 Mid-Semester Exam", "2026-09-24", "11:00"),
    (15, 5, "23456 Mid-Semester Exam", "2026-09-29", "14:00"),
    (16, 6, "34567 Mid-Semester Exam", "2026-10-01", "10:00"),
    (17, 7, "45678 Mid-Semester Exam", "2026-10-06", "13:00"),
    (18, 8, "56789 Mid-Semester Exam", "2026-10-08", "09:00"),
    (19, 9, "67890 Mid-Semester Exam", "2026-10-13", "11:00"),
    (20, 10, "78901 Mid-Semester Exam", "2026-10-15", "14:00")
]


cursor.executemany(
    """
    INSERT INTO course_exams (
        course_exam_id,
        course_id,
        exam_name,
        exam_date,
        exam_time
    )
    VALUES (?, ?, ?, ?, ?)
    """,
    course_exams
)


# ==================================================
# INITIAL STUDENT EXAMS
# ==================================================

student_exams = []


cursor.executemany(
    """
    INSERT INTO student_exams (
        exam_id,
        course_exam_id,
        course_id,
        student_id,
        exam_name,
        exam_date,
        exam_time,
        status,
        is_deleted
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    student_exams
)


conn.commit()
conn.close()



print(
    "Database initialized with course_exams and student_exams."
)
