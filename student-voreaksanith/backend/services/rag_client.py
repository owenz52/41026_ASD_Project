"""Client for the shared RAG server.

The shared server (ai-services/rag-server) is stateless: the calling feature
supplies the documents to search, so the calendar sends chunks built from its
own events by rag_documents.

Wire format
-----------
    POST /answer   {"query", "feature", "student_id", "documents", "k"}
    POST /retrieve same body, returns the retrieved chunks without an answer
    GET  /health

An answer comes back as:
    {"status": "success" | "insufficient_context",
     "answer": str,
     "citations": [source_id, ...],
     "confidence": "Context Available" | "Insufficient Context",
     "sources": [{"chunk_id", "source_id", "authority_tier", "text"}, ...]}

The server already refuses to answer without citations — its answer step
returns insufficient_context when the model cites nothing. This client keeps
the same check on the calendar's side, because an answer presented as
grounded when nothing supports it is the one failure worth guarding twice.

The server's two confidence labels are mapped onto the four categories the
frontend uses. The server only says whether context was available, so the level
is worked out here from how much of the student's question the cited record
covers (see rag_text). It used to count the cited sources, but an answer is
nearly always drawn from one record, so nearly every answer read "low" whether
or not it was right.
"""
import requests

from config import (
    RAG_ENABLED,
    RAG_FEATURE,
    RAG_SERVER_URL,
    RAG_TIMEOUT_SECONDS,
    RAG_TOP_K,
)
from services import rag_documents, rag_text

INSUFFICIENT_MESSAGE = (
    "There is not enough relevant material in your calendar to answer this "
    "question. No answer has been generated, because any answer would not be "
    "grounded in retrieved context."
)


def _base():
    return RAG_SERVER_URL.rstrip("/")


def _insufficient(reason, citations=None, searched=None):
    return {
        "ok": True,
        "available": True,
        "grounded": False,
        "answer": INSUFFICIENT_MESSAGE,
        "citations": citations or [],
        "confidence": "insufficient",
        "server_confidence": "Insufficient Context",
        "reason": reason,
        "searched": searched or {},
    }


def _unavailable(error, searched=None):
    return {
        "ok": False,
        "available": False,
        "grounded": False,
        "answer": None,
        "citations": [],
        "confidence": "insufficient",
        "error": f"RAG server unreachable at {_base()}: {error}",
        "searched": searched or {},
    }


def _cited_texts(body):
    """The full text of every record the answer cited."""
    cited = set(body.get("citations") or [])
    return [source.get("text") or ""
            for source in (body.get("sources") or [])
            if source.get("source_id") in cited]


def _assess(server_label, question, body, citation_count):
    """(level, basis, coverage) for an answer.

    The level reflects how much of the question the cited record covers, not
    how many records were cited. The basis is the same fact in words, so the
    student can see why the label is what it is.
    """
    if str(server_label).strip().lower().startswith("insufficient"):
        return "insufficient", None, None

    coverage = rag_text.coverage(question, _cited_texts(body))
    return (rag_text.level(coverage),
            rag_text.basis(coverage, citation_count),
            coverage)


def _citations(body):
    """Pair each cited source_id with the text that supports it."""
    cited = body.get("citations") or []
    sources = {s.get("source_id"): s for s in (body.get("sources") or [])}

    citations = []
    for source_id in cited:
        source = sources.get(source_id, {})
        citations.append({
            "source": source_id,
            "snippet": (source.get("text") or "")[:300],
            "score": None,
            "authority_tier": source.get("authority_tier"),
        })
    return citations


def ask(question, top_k=None):
    """Ask the shared RAG server a question about the student's calendar."""
    if not RAG_ENABLED:
        return {"ok": False, "available": False, "grounded": False,
                "answer": None, "citations": [], "confidence": "insufficient",
                "error": "RAG is disabled in this environment"}

    if not question or not str(question).strip():
        return {"ok": False, "available": True, "grounded": False,
                "answer": None, "citations": [], "confidence": "insufficient",
                "error": "question is required"}

    question = str(question).strip()

    # The server caps the query at 1000 characters and rejects the request
    # outright if it is longer.
    if len(question) > 1000:
        question = question[:1000]

    return _ask_for(question, None, top_k)


def ask_for_student(question, student_id, top_k=None):
    """Ask about one student's calendar, supplying that student's documents."""
    if not RAG_ENABLED:
        return {"ok": False, "available": False, "grounded": False,
                "answer": None, "citations": [], "confidence": "insufficient",
                "error": "RAG is disabled in this environment"}

    if not question or not str(question).strip():
        return {"ok": False, "available": True, "grounded": False,
                "answer": None, "citations": [], "confidence": "insufficient",
                "error": "question is required"}

    return _ask_for(str(question).strip()[:1000], student_id, top_k)


def _ask_for(question, student_id, top_k):
    documents, report = rag_documents.build_documents(
        student_id, question=question)

    if report.get("error"):
        return _unavailable(report["error"], report)

    # With nothing to search there is no grounded answer to be had, and the
    # server would return insufficient_context anyway.
    if not documents:
        if report.get("upcoming_only") and report.get("left_out"):
            reason = (f"there is nothing upcoming to search; "
                      f"{report['left_out']} past or completed item(s) were left out")
        else:
            reason = "there are no calendar events to search"
        return _insufficient(reason, searched=report)

    payload = {
        "query": question,
        "feature": RAG_FEATURE,
        "student_id": documents[0]["student_id"],
        "documents": documents,
        # The server accepts k between 1 and 10.
        "k": max(1, min(int(top_k or RAG_TOP_K), 10)),
    }

    try:
        response = requests.post(f"{_base()}/answer", json=payload,
                                 timeout=RAG_TIMEOUT_SECONDS)
        body = response.json()
    except (requests.RequestException, ValueError) as error:
        return _unavailable(type(error).__name__, report)

    if response.status_code >= 400:
        message = (body.get("message") if isinstance(body, dict)
                   else f"server returned {response.status_code}")
        # A 502 from the shared server means its Ollama was unavailable.
        return _unavailable(message, report)

    if not isinstance(body, dict):
        return _unavailable("unexpected response shape", report)

    citations = _citations(body)
    answer = (body.get("answer") or "").strip()
    confidence, basis, coverage = _assess(
        body.get("confidence"), question, body, len(citations))

    if body.get("status") == "insufficient_context":
        return _insufficient(
            "the shared RAG server found no relevant context",
            citations, report)

    # Guarded on this side as well: an answer with nothing supporting it is
    # not presented as grounded.
    if not citations:
        return _insufficient("the answer cited no sources", searched=report)

    if not answer:
        return _insufficient("no answer was returned", citations, report)

    return {
        "ok": True,
        "available": True,
        "grounded": True,
        "answer": answer,
        "citations": citations,
        "citation_count": len(citations),
        "confidence": confidence,
        "confidence_basis": basis,
        "coverage": coverage,
        "server_confidence": body.get("confidence"),
        "question": question,
        "searched": report,
    }


def health():
    """Whether the shared RAG server is reachable, for the diagnostics view."""
    if not RAG_ENABLED:
        return {"enabled": False, "reachable": False, "url": _base(),
                "reason": "disabled by configuration"}

    try:
        response = requests.get(f"{_base()}/health",
                                timeout=RAG_TIMEOUT_SECONDS)
        return {"enabled": True, "reachable": response.status_code < 400,
                "url": _base(), "status": response.status_code}
    except requests.RequestException as error:
        return {"enabled": True, "reachable": False, "url": _base(),
                "error": type(error).__name__}
