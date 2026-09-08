from flask import Blueprint, request, jsonify

from db_connection import get_db_connection


sync_exam_bp = Blueprint(
    "sync_exams",
    __name__
)


# ==================================================
# SYNC STUDENT EXAMS
# ==================================================

@sync_exam_bp.post("/exams/sync")
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

    # --------------------------------------------------
    # Validate student ID
    # --------------------------------------------------

    if not student_id:

        return jsonify({
            "error": "student_id required"
        }), 400

    # --------------------------------------------------
    # Allow null course_ids
    # --------------------------------------------------

    if course_ids is None:
        course_ids = []

    # --------------------------------------------------
    # course_ids must be a list
    # --------------------------------------------------

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
        # 1. REMOVE COURSE-GENERATED EXAMS FROM
        #    COURSES THE STUDENT IS NO LONGER ENROLLED IN
        #
        # Only exams with a course_exam_id are considered
        # course-generated exams.
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
            # Student has no enrolled courses.
            #
            # Remove course-generated exams only.
            #
            # Manually added exams remain because their
            # course_exam_id is NULL.
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