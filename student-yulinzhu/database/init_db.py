import os
import sqlite3

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DATABASE_NAME = os.path.join(DATA_DIR, "enrolment.db")

os.makedirs(DATA_DIR, exist_ok=True)

conn = sqlite3.connect(
    DATABASE_NAME
)

cursor = conn.cursor()

cursor.execute("PRAGMA foreign_keys = ON")

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS courses (
        course_id INTEGER PRIMARY KEY,
        course_name TEXT NOT NULL,
        course_code TEXT NOT NULL,
        description TEXT NOT NULL,
        availability INTEGER NOT NULL
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS enrolments (
        enrolment_id INTEGER PRIMARY KEY,
        student_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        enrolment_status TEXT NOT NULL,
        enrolment_date TEXT NOT NULL,
        FOREIGN KEY (course_id) REFERENCES courses (course_id)
    )
    """
)

cursor.execute("DELETE FROM enrolments")
cursor.execute("DELETE FROM courses")

courses = [
    (1, "41026", "Advanced Software Development", "Software development with Agent AI", 1),
    (2, "48024", "Programming 2", "This subject teaches concepts, theories and technologies underlying the methods and techniques of OOP programming and GUI programming", 1),
    (3, "31271", "Database Fundamentals", "This subject lays the foundation for effective database systems, teaching you how data is structured and managed within organizations, ensuring its usability for applications and users.", 1),
    (4, "12345", "Fundamentals Of Japanese", "An introductory course on the Japanese language.", 1),
    (5, "23456", "Philosophy Theory", "An introduction to philosophical concepts and theories.", 1),
    (6, "34567", "Modern Art", "Exploring the evolution of art in the modern era.", 1),
    (7, "45678", "Environmental Science", "Understanding the impact of human activities on the environment.", 1),
    (8, "56789", "Digital Marketing", "Strategies and techniques for marketing in the digital age.", 1),
    (9, "67890", "Cybersecurity Basics", "An overview of cybersecurity principles and practices.", 1),
    (10, "78901", "Data Science Introduction", "An introduction to data science concepts and methodologies.", 1),
]

cursor.executemany(
    """
    INSERT INTO courses (
        course_id,
        course_code,
        course_name,
        description,
        availability
    )
    VALUES (?, ?, ?, ?, ?)
    """,
    courses
)

enrolments = [
    (1, 1001, 1, "enrolled", "2026-08-22"),
    (2, 1002, 2, "enrolled", "2026-08-21"),
    (3, 1003, 3, "enrolled", "2026-08-23"),
    (4, 1004, 4, "enrolled", "2026-08-25"),
    (5, 1005, 5, "enrolled", "2026-08-26"),
    (6, 1006, 6, "enrolled", "2026-08-19"),
    (7, 1007, 7, "enrolled", "2026-08-20"),
    (8, 1008, 8, "enrolled", "2026-08-12"),
    (9, 1009, 9, "enrolled", "2026-08-16"),
    (10, 1010, 10, "enrolled", "2026-08-17"),
]

cursor.executemany(
    """
    INSERT INTO enrolments (
        enrolment_id,
        student_id,
        course_id,
        enrolment_status,
        enrolment_date
    )
    VALUES (?, ?, ?, ?, ?)
    """,
    enrolments
)

conn.commit()
conn.close()

print("Database initialized successfully.")
print("10 courses added")
print("10 enrolments added")
print("Database:", DATABASE_NAME)