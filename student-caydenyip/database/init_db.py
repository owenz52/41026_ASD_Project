import os
import sqlite3

DATA_DIR = "/app/data"
DATABASE_NAME = os.path.join(DATA_DIR, "exam.db")

os.makedirs(DATA_DIR, exist_ok=True)

conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS exams (
    exam_id INTEGER PRIMARY KEY,
    course_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    exam_name TEXT NOT NULL,
    exam_date DATE NOT NULL,
    exam_time TIME NOT NULL,
    status TEXT NOT NULL
)
""")

cursor.execute("DELETE FROM exams")

exams = [
    (1, 101, 1, "ASD101 Final Exam", "2026-11-10", "09:00", "Uncompleted"),
    (2, 101, 2, "ASD101 Final Exam", "2026-11-10", "09:00", "Uncompleted"),
    (3, 201, 3, "WEB201 Final Exam", "2026-11-12", "13:00", "Uncompleted"),
    (4, 201, 4, "WEB201 Final Exam", "2026-11-12", "13:00", "Uncompleted"),
    (5, 101, 5, "DBS101 Final Exam", "2026-11-14", "09:00", "Uncompleted"),
    (6, 101, 6, "DBS101 Final Exam", "2026-11-14", "09:00", "Uncompleted"),
    (7, 201, 7, "NET201 Final Exam", "2026-11-16", "13:00", "Uncompleted"),
    (8, 201, 8, "NET201 Final Exam", "2026-11-16", "13:00", "Uncompleted"),
    (9, 301, 9, "SEC301 Final Exam", "2026-11-18", "10:00", "Uncompleted"),
    (10, 301, 10, "SEC301 Final Exam", "2026-11-18", "10:00", "Uncompleted")
]


cursor.executemany("""
INSERT INTO exams (
    exam_id,
    course_id,
    student_id,
    exam_name,
    exam_date,
    exam_time,
    status
)
VALUES (?, ?, ?, ?, ?, ?, ?)
""", exams)

conn.commit()
conn.close()

print("Database initialized with 10 exams.")
