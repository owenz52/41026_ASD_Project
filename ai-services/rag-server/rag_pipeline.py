import hashlib
import re
import uuid

import chromadb


VECTOR_SIZE = 256
STOPWORDS = {
    "a", "an", "and", "are", "do", "for", "how", "i", "in",
    "is", "me", "my", "of", "on", "should", "the", "to",
    "what", "which", "with",
}


def words(text: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-z0-9]+", text.lower())
        if word not in STOPWORDS
    }


def embed(text: str) -> list[float]:
    """Create a small, local token-based vector for Chroma."""
    vector = [0.0] * VECTOR_SIZE

    for word in words(text):
        digest = hashlib.sha256(word.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % VECTOR_SIZE
        vector[index] += 1.0

    length = sum(value * value for value in vector) ** 0.5

    if length:
        vector = [value / length for value in vector]

    return vector


def retrieve_context(
    query: str,
    feature: str,
    student_id: int,
    documents: list[dict],
    k: int = 5,
) -> dict:
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 1000:
        raise ValueError("query must contain 1–1000 characters")

    if not re.fullmatch(r"[a-z][a-z0-9_-]{1,31}", feature):
        raise ValueError("invalid feature")

    if type(student_id) is not int or student_id <= 0:
        raise ValueError("student_id must be a positive integer")

    if type(k) is not int or not 1 <= k <= 10:
        raise ValueError("k must be between 1 and 10")

    if not isinstance(documents, list) or len(documents) > 100:
        raise ValueError("documents must be a list of at most 100 items")

    seen_ids = set()

    for document in documents:
        if not isinstance(document, dict):
            raise ValueError("each document must be an object")

        for field in ("chunk_id", "source_id", "text"):
            if not isinstance(document.get(field), str) or not document[field].strip():
                raise ValueError(f"document requires {field}")

        if document.get("feature") != feature:
            raise ValueError("document feature does not match request feature")

        if document.get("student_id") != student_id:
            raise ValueError("document student_id does not match request student_id")

        if len(document["text"]) > 2000:
            raise ValueError("document text exceeds 2000 characters")

        if document["chunk_id"] in seen_ids:
            raise ValueError("duplicate chunk_id")

        seen_ids.add(document["chunk_id"])

    if not documents or not words(query):
        return {
            "status": "success",
            "query": query,
            "retrieval_mode": "vector_with_relevance_filter",
            "k": k,
            "results": [],
        }

    client = chromadb.EphemeralClient()
    collection_name = f"rag_{uuid.uuid4().hex}"
    collection = client.create_collection(name=collection_name)

    try:
        collection.add(
            ids=[document["chunk_id"] for document in documents],
            documents=[document["text"] for document in documents],
            embeddings=[embed(document["text"]) for document in documents],
            metadatas=[
                {
                    "source_id": document["source_id"],
                    "authority_tier": document.get("authority_tier", "tier_2"),
                }
                for document in documents
            ],
        )

        matches = collection.query(
            query_embeddings=[embed(query)],
            n_results=len(documents),
            include=["documents", "metadatas", "distances"],
        )

        ranked = []

        for chunk_id, text, metadata, distance in zip(
            matches["ids"][0],
            matches["documents"][0],
            matches["metadatas"][0],
            matches["distances"][0],
        ):
            matched_terms = len(words(query) & words(text))

            # Vector similarity alone can return irrelevant chunks.
            if matched_terms == 0:
                continue

            ranked.append({
                "chunk_id": chunk_id,
                "source_id": metadata["source_id"],
                "authority_tier": metadata["authority_tier"],
                "distance": distance,
                "text": text,
                "matched_terms": matched_terms,
            })

        ranked.sort(
            key=lambda result: (-result["matched_terms"], result["distance"])
        )

        results = [
            {"rank": index, **result}
            for index, result in enumerate(ranked[:k], start=1)
        ]

        return {
            "status": "success",
            "query": query,
            "retrieval_mode": "vector_with_relevance_filter",
            "k": k,
            "results": results,
        }

    finally:
        client.delete_collection(name=collection_name)