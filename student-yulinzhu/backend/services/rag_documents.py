def build_course_documents(
        courses: list[dict],
        student_id: int,
) -> list[dict]:
    """Map public course records to the shared RAG document format."""
    if type(student_id) is not int or student_id <= 0:
        raise ValueError("student_id must be a positive integer")

    documents = []
    for course in courses:
        source_id = f"course:{course['course_id']}"
        availability = (
            "available" if course["availability"] == 1 else "unavailable"
        )
        documents.append({
            "feature": "enrolment",
            "source_id": source_id,
            "student_id": student_id,
            "chunk_id": source_id,
            "authority_tier": "tier_1",
            "text": (
                f"Course code: {course['course_code']}\n"
                f"Course name: {course['course_name']}\n"
                f"Description: {course['description']}\n"
                f"Availability: {availability}\n"
            ),
        })
    return documents