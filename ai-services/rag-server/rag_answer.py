import re

import requests


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:0.5b"
INSUFFICIENT_ANSWER = "I don't have enough relevant context to answer that."


def insufficient_context() -> dict:
    return {
        "status": "insufficient_context",
        "answer": INSUFFICIENT_ANSWER,
        "citations": [],
        "confidence": "Insufficient Context",
    }


def answer_with_context(query: str, retrieval: dict) -> dict:
    results = retrieval.get("results", [])
    if not results:
        return insufficient_context()

    sources = list(dict.fromkeys(item["source_id"] for item in results))
    context = "\n\n".join(
        f"Source [{item['source_id']}]:\n{item['text']}"
        for item in results
    )

    prompt = f"""Answer using only the provided context.
Cite each fact with its source ID in square brackets, for example [assessment:11].
Use only source IDs shown in the context.
If the context does not answer the question, reply exactly:
{INSUFFICIENT_ANSWER}

Context:
{context}

Question: {query}
Answer:"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0},
        },
        timeout=60,
    )
    response.raise_for_status()
    answer = response.json().get("response", "").strip()

    if not answer or INSUFFICIENT_ANSWER.lower() in answer.lower():
        return insufficient_context()

    citations = [
        source_id
        for source_id in sources
        if re.search(r"\[" + re.escape(source_id) + r"\]", answer)
    ]
    if not citations:
        return insufficient_context()

    return {
        "status": "success",
        "answer": answer,
        "citations": citations,
        "confidence": "Context Available",
    }