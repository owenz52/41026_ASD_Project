def build_note_documents(
    student_id: int,
    notebooks: list[dict],
    notes_by_notebook: dict[int, list[dict]],
) -> list[dict]:
    """Map one student's notes to the shared RAG document format."""
    if type(student_id) is not int or student_id <= 0:
        raise ValueError("student_id must be a positive integer")

    documents = []

    for notebook in notebooks:
        if notebook.get("student_id") != student_id:
            continue

        for note in notes_by_notebook.get(notebook["notebook_id"], []):
            source_id = f"note:{note['note_id']}"
            content = str(note.get("note_content") or "")[:1500]

            text = "\n".join([
                f"Notebook: {notebook.get('notebook_title', '')}",
                f"Course: {notebook.get('course_id', '')}",
                f"Note title: {note.get('note_title', '')}",
                f"Updated: {note.get('updated_date', '')}",
                f"Content: {content}",
            ])

            documents.append({
                "feature": "notebook",
                "student_id": student_id,
                "chunk_id": source_id,
                "source_id": source_id,
                "authority_tier": "tier_1",
                "text": text[:2000],
                "updated_date": note.get("updated_date", ""),
            })

    # The shared RAG server accepts at most 100 documents per request,
    # so keep the most recently updated notes.
    documents.sort(key=lambda document: document["updated_date"], reverse=True)

    for document in documents:
        document.pop("updated_date", None)

    return documents[:100]
