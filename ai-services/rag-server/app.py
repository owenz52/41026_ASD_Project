"""Shared RAG server.

Answers questions about the project's own data, grounded in retrieved context
and returned with the sources the answer was drawn from and a confidence
category.

The central rule is that the model may only answer from retrieved passages.
Retrieval happens first; if nothing relevant is found, the model is never
called and an insufficient-context response is returned instead. An answer
that is not supported by retrieved material is worse than no answer, so that
path is a refusal rather than a guess.

Contract
--------
    GET  /health     -> liveness, passage count and index report
    POST /query      -> {"question": str, "top_k": int, "feature": str}
    POST /reindex    -> rebuild the index from the feature services
    GET  /documents  -> what the index was built from

If Ollama is unavailable the server still answers, by returning the retrieved
passages themselves rather than a written summary. The answer stays grounded;
only the phrasing is lost, and the response says so.
"""
import os
import threading

import requests
from flask import Flask, jsonify, request

from corpus import build_index
from retrieval import confidence_from

app = Flask(__name__)

PORT = int(os.getenv("RAG_PORT", 5200))
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", 45))
DEFAULT_TOP_K = int(os.getenv("RAG_TOP_K", 4))

PROMPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")

INSUFFICIENT_MESSAGE = (
    "There is not enough relevant material in the knowledge base to answer "
    "this question. No answer has been generated, because any answer would "
    "not be grounded in retrieved context."
)

_lock = threading.Lock()
_index = None
_report = {}


def load_prompt(name):
    with open(os.path.join(PROMPT_DIR, name), encoding="utf-8") as handle:
        return handle.read().strip()


def reindex(student_id=None):
    global _index, _report
    with _lock:
        _index, _report = build_index(student_id)
    return _report


def _format_context(results):
    """Number the passages so the model can cite them by index."""
    return "\n\n".join(
        f"[{i + 1}] (source: {r['source']})\n{r['text']}"
        for i, r in enumerate(results))


def _ask_model(question, results):
    """Write an answer from the retrieved passages. Returns (answer, error)."""
    try:
        system_prompt = load_prompt("system_prompt.txt")
        task_prompt = (load_prompt("query_prompt.txt")
                       .replace("{{QUESTION}}", question)
                       .replace("{{CONTEXT}}", _format_context(results)))
    except OSError as error:
        return None, f"prompt file unavailable: {error}"

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={"model": OLLAMA_MODEL,
                  "messages": [{"role": "system", "content": system_prompt},
                               {"role": "user", "content": task_prompt}],
                  "stream": False},
            timeout=OLLAMA_TIMEOUT)
        response.raise_for_status()
        answer = response.json()["message"]["content"].strip()
    except (requests.RequestException, KeyError, ValueError) as error:
        return None, f"model unavailable: {type(error).__name__}"

    return answer, None


def _extractive_answer(results):
    """The retrieved material itself, used when the model cannot be reached.

    Still grounded: every sentence comes from an indexed passage.
    """
    lines = [r["text"] for r in results[:2]]
    return " ".join(lines)


def _citations(results):
    return [{"source": r["source"],
             "snippet": r["text"][:300],
             "score": r["score"]} for r in results]


# ------------------------------------------------------------------ routes

@app.get("/health")
def health():
    if _index is None:
        reindex()
    return jsonify({"status": "ok", "passages": len(_index), "index": _report})


@app.get("/documents")
def documents():
    if _index is None:
        reindex()
    return jsonify({"passages": len(_index), "index": _report})


@app.post("/reindex")
def reindex_route():
    data = request.get_json(silent=True) or {}
    report = reindex(data.get("student_id"))
    return jsonify({"reindexed": True, "index": report})


@app.post("/query")
def query():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()

    if not question:
        return jsonify({"error": "'question' is required"}), 400

    if _index is None:
        reindex()

    top_k = int(data.get("top_k") or DEFAULT_TOP_K)
    results = _index.search(question, top_k=top_k)

    # Retrieval first. With no relevant context the model is never called.
    if not results:
        return jsonify({
            "grounded": False,
            "insufficient_context": True,
            "answer": INSUFFICIENT_MESSAGE,
            "citations": [],
            "confidence": "insufficient",
            "question": question,
            "reason": "no passage in the knowledge base matched the question",
        })

    confidence = confidence_from(results)
    answer, error = _ask_model(question, results)

    if answer is None:
        # Grounded, but not written up by the model.
        return jsonify({
            "grounded": True,
            "answer": _extractive_answer(results),
            "citations": _citations(results),
            "confidence": confidence,
            "question": question,
            "generated": False,
            "note": f"Answer assembled from retrieved passages ({error}).",
        })

    # The model is instructed to say so when the context does not answer the
    # question; that is honoured rather than shown as an answer.
    if "INSUFFICIENT_CONTEXT" in answer.upper():
        return jsonify({
            "grounded": False,
            "insufficient_context": True,
            "answer": INSUFFICIENT_MESSAGE,
            "citations": _citations(results),
            "confidence": "insufficient",
            "question": question,
            "reason": "retrieved context did not answer the question",
        })

    return jsonify({
        "grounded": True,
        "answer": answer,
        "citations": _citations(results),
        "confidence": confidence,
        "question": question,
        "generated": True,
        "feature": data.get("feature"),
    })


if __name__ == "__main__":
    report = reindex()
    print(f"Shared RAG server on http://localhost:{PORT}")
    print(f"  indexed {report['passages']} passage(s)")
    for name, count in report["sources"].items():
        print(f"    {name}: {count}")
    for missing in report["unavailable"]:
        print(f"    unavailable: {missing['source']} ({missing['reason']})")
    app.run(host="0.0.0.0", port=PORT)
