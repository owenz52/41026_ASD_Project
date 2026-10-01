from flask import Blueprint, request, jsonify

from db_connection import get_db_connection


post_exam_bp = Blueprint(
    "post_exams",
    __name__
)


# ==================================================
# ADD EXAM
# ==================================================

@post_exam_bp.post("/exams")
def add_exam():

    data = request.get_json(
        silent=True
    ) or {}

    student_id = data.get("student_id")
    course_id = data.get("course_id")
    exam_name = data.get("exam_name")
    exam_date = data.get("exam_date")
    exam_time = data.get("exam_time")

    # --------------------------------------------------
    # Validate required fields
    # --------------------------------------------------

    if student_id is None or str(student_id).strip() == "":
        return jsonify({
            "error": "student_id required"
        }), 400

    if course_id is None or str(course_id).strip() == "":
        return jsonify({
            "error": "course_id required"
        }), 400

    if exam_name is None or str(exam_name).strip() == "":
        return jsonify({
            "error": "exam_name required"
        }), 400

    if exam_date is None or str(exam_date).strip() == "":
        return jsonify({
            "error": "exam_date required"
        }), 400

    if exam_time is None or str(exam_time).strip() == "":
        return jsonify({
            "error": "exam_time required"
        }), 400

    conn = get_db_connection()

    try:

        # --------------------------------------------------
        # Manually added exams do NOT have a course_exam_id.
        #
        # course_exam_id is therefore NULL.
        # --------------------------------------------------

        cursor = conn.execute(
            """
            INSERT INTO student_exams (
                course_exam_id,
                course_id,
                student_id,
                exam_name,
                exam_date,
                exam_time,
                status,
                is_deleted
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                None,
                course_id,
                student_id,
                exam_name,
                exam_date,
                exam_time,
                "Uncompleted",
                0
            )
        )

        conn.commit()

        exam_id = cursor.lastrowid

        return jsonify({
            "message": "Exam added successfully.",
            "exam_id": exam_id
        }), 201

    except Exception as exc:

        conn.rollback()

        return jsonify({
            "error": "Failed to add exam.",
            "details": str(exc)
        }), 500

    finally:

        conn.close()


# ==================================================
# RESET STUDENT EXAMS
# ==================================================

@post_exam_bp.post("/exams/reset")
def reset_exams():

    student_id = request.args.get(
        "student_id",
        ""
    ).strip()

    data = request.get_json(
        silent=True
    ) or {}

    course_ids = data.get(
        "course_ids",
        []
    )

    if not student_id:

        return jsonify({
            "error": "student_id required"
        }), 400

    if course_ids is None:
        course_ids = []

    if not isinstance(course_ids, list):

        return jsonify({
            "error": "course_ids must be a list"
        }), 400

    # --------------------------------------------------
    # Remove null course IDs
    # --------------------------------------------------

    course_ids = [
        course_id
        for course_id in course_ids
        if course_id is not None
    ]

    conn = get_db_connection()

    try:

        # --------------------------------------------------
        # Delete ALL existing exams for this student
        # --------------------------------------------------

        conn.execute(
            """
            DELETE FROM student_exams
            WHERE student_id = ?
            """,
            (student_id,)
        )

        created = 0

        # --------------------------------------------------
        # Re-create exams from the student's courses
        # --------------------------------------------------

        for course_id in course_ids:

            course_exams = conn.execute(
                """
                SELECT
                    course_exam_id,
                    course_id,
                    exam_name,
                    exam_date,
                    exam_time
                FROM course_exams
                WHERE course_id = ?
                ORDER BY exam_date, exam_time
                """,
                (course_id,)
            ).fetchall()

            for course_exam in course_exams:

                conn.execute(
                    """
                    INSERT INTO student_exams (
                        course_exam_id,
                        course_id,
                        student_id,
                        exam_name,
                        exam_date,
                        exam_time,
                        status,
                        is_deleted
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        course_exam["course_exam_id"],
                        course_exam["course_id"],
                        student_id,
                        course_exam["exam_name"],
                        course_exam["exam_date"],
                        course_exam["exam_time"],
                        "Uncompleted",
                        0
                    )
                )

                created += 1

        conn.commit()

        return jsonify({
            "message": "Exams reset successfully.",
            "student_id": student_id,
            "exams_created": created
        }), 200

    except Exception as exc:

        conn.rollback()

        return jsonify({
            "error": "Failed to reset exams.",
            "details": str(exc)
        }), 500

    finally:

        conn.close()


# ==================================================
# SYNC STUDENT EXAMS
# ==================================================

@post_exam_bp.post("/exams/sync")
def sync_exams():

    student_id = request.args.get(
        "student_id",
        ""
    ).strip()

    data = request.get_json(
        silent=True
    ) or {}

    course_ids = data.get(
        "course_ids",
        []
    )

    if not student_id:

        return jsonify({
            "error": "student_id required"
        }), 400

    if course_ids is None:
        course_ids = []

    if not isinstance(course_ids, list):

        return jsonify({
            "error": "course_ids must be a list"
        }), 400

    # --------------------------------------------------
    # Remove null course IDs
    # --------------------------------------------------

    course_ids = [
        course_id
        for course_id in course_ids
        if course_id is not None
    ]

    # --------------------------------------------------
    # Remove duplicate course IDs
    # --------------------------------------------------

    course_ids = list(
        dict.fromkeys(course_ids)
    )

    conn = get_db_connection()

    try:

        added = 0
        skipped = 0
        removed = 0

        # ==================================================
        # 1. REMOVE COURSE-GENERATED EXAMS FROM COURSES
        #    THE STUDENT IS NO LONGER ENROLLED IN
        #
        # course_exam_id IS NOT NULL means the exam was
        # generated from a course_exam.
        #
        # Manually added exams have course_exam_id = NULL
        # and are therefore protected.
        # ==================================================

        if course_ids:

            placeholders = ",".join(
                "?" for _ in course_ids
            )

            cursor = conn.execute(
                f"""
                DELETE FROM student_exams

                WHERE student_id = ?

                  AND course_id NOT IN ({placeholders})

                  AND course_exam_id IS NOT NULL
                """,
                (
                    student_id,
                    *course_ids
                )
            )

            removed = cursor.rowcount

        else:

            # --------------------------------------------------
            # No enrolled courses.
            #
            # Remove course-generated exams only.
            #
            # Manually added exams remain.
            # --------------------------------------------------

            cursor = conn.execute(
                """
                DELETE FROM student_exams

                WHERE student_id = ?

                  AND course_exam_id IS NOT NULL
                """,
                (student_id,)
            )

            removed = cursor.rowcount

        # ==================================================
        # 2. ADD MISSING EXAMS FOR CURRENT COURSES
        # ==================================================

        for course_id in course_ids:

            course_exams = conn.execute(
                """
                SELECT
                    course_exam_id,
                    course_id,
                    exam_name,
                    exam_date,
                    exam_time
                FROM course_exams
                WHERE course_id = ?
                ORDER BY exam_date, exam_time
                """,
                (course_id,)
            ).fetchall()

            # ==================================================
            # 3. CHECK EACH COURSE EXAM
            # ==================================================

            for course_exam in course_exams:

                existing_exam = conn.execute(
                    """
                    SELECT
                        exam_id,
                        is_deleted

                    FROM student_exams

                    WHERE student_id = ?

                      AND course_exam_id = ?
                    """,
                    (
                        student_id,
                        course_exam["course_exam_id"]
                    )
                ).fetchone()

                # --------------------------------------------------
                # Existing exam.
                #
                # This includes soft-deleted exams.
                #
                # Therefore a deleted course exam will NOT
                # be recreated by sync.
                # --------------------------------------------------

                if existing_exam:

                    skipped += 1

                    continue

                # ==================================================
                # 4. ADD MISSING COURSE EXAM
                # ==================================================

                conn.execute(
                    """
                    INSERT INTO student_exams (
                        course_exam_id,
                        course_id,
                        student_id,
                        exam_name,
                        exam_date,
                        exam_time,
                        status,
                        is_deleted
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        course_exam["course_exam_id"],
                        course_exam["course_id"],
                        student_id,
                        course_exam["exam_name"],
                        course_exam["exam_date"],
                        course_exam["exam_time"],
                        "Uncompleted",
                        0
                    )
                )

                added += 1

        # ==================================================
        # 5. COMMIT
        # ==================================================

        conn.commit()

        return jsonify({
            "message": "Exams synchronized successfully.",
            "student_id": student_id,
            "courses": course_ids,
            "exams_added": added,
            "exams_removed": removed,
            "exams_already_existing": skipped
        }), 200

    except Exception as exc:

        conn.rollback()

        return jsonify({
            "error": "Failed to synchronize exams.",
            "details": str(exc)
        }), 500

    finally:

        conn.close()