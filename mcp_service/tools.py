import os
import sqlite3

import os
import sqlite3

from pathlib import Path
import sqlite3

DATABASE_NAME = Path(__file__).parent.parent / "data" / "exam.db"

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_student_exams(student_id: int):

    if not student_id:
        return {
            "error": "student_id is required"
        }

    conn = None

    try:

        conn = get_db_connection()

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                exam_id,
                course_exam_id,
                course_id,
                student_id,
                exam_name,
                exam_date,
                exam_time,
                status,
                is_deleted
            FROM student_exams
            WHERE student_id = ?
            AND is_deleted = 0
            ORDER BY exam_date, exam_time
            """,
            (student_id,)
        )

        rows = cursor.fetchall()

        exams = [
            dict(row)
            for row in rows
        ]

        return exams

    except Exception as error:

        return {
            "error": "Failed to get student exams",
            "details": str(error)
        }

    finally:

        if conn:
            conn.close()


def get_student_exam_status(student_id: int):

    if not student_id:
        return {
            "error": "student_id is required"
        }

    try:

        exams = get_student_exams(
            student_id
        )

        if isinstance(exams, dict) and "error" in exams:
            return exams

        completed_exams = 0
        non_completed_exams = 0

        for exam in exams:

            if exam.get("is_deleted", 0):
                continue

            status = str(
                exam.get("status", "")
            ).strip().lower()

            if status == "completed":
                completed_exams += 1
            else:
                non_completed_exams += 1

        total_exams = (
            completed_exams +
            non_completed_exams
        )

        return {
            "student_id": student_id,
            "total_exams": total_exams,
            "completed_exams": completed_exams,
            "non_completed_exams": non_completed_exams,
        }

    except Exception as error:

        return {
            "error": "Failed to determine exam status",
            "details": str(error)
        }


def get_student_exam_summary(student_id: int):

    if not student_id:
        return {
            "error": "student_id is required"
        }

    try:

        exams = get_student_exams(
            student_id
        )

        if isinstance(exams, dict) and "error" in exams:
            return exams

        exam_status = get_student_exam_status(
            student_id
        )

        if isinstance(exam_status, dict) and "error" in exam_status:
            return exam_status

        return {
            "student_id": student_id,

            "exam_summary": {
                "total_exams": exam_status.get(
                    "total_exams",
                    0
                ),

                "completed_exams": exam_status.get(
                    "completed_exams",
                    0
                ),

                "non_completed_exams": exam_status.get(
                    "non_completed_exams",
                    0
                ),
            },

            "exams": exams,
        }

    except Exception as error:

        return {
            "error": "Failed to create student exam summary",
            "details": str(error)
        }


if __name__ == "__main__":

    test_student_id = 123

    print("\nSTUDENT EXAMS")

    print(
        get_student_exams(
            test_student_id
        )
    )

    print("\nEXAM STATUS")

    print(
        get_student_exam_status(
            test_student_id
        )
    )

    print("\nCOMPLETE SUMMARY")

    print(
        get_student_exam_summary(
            test_student_id
        )
    )
