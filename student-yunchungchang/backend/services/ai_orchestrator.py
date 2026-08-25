import re
from collections import Counter
from pathlib import Path

import requests

from config import OLLAMA_MODEL, get_cfg
from services.database_api import get_note, search_notes
from services.llm_client import ask_llm
from services.prompt_loader import load_prompt, render_prompt

STOPWORDS_PATH = Path(__file__).resolve().parent / "stopwords.txt"
STOPWORDS = set(STOPWORDS_PATH.read_text(encoding="utf-8").split())

WORD_RE = re.compile(r"[a-zA-Z]+")

PROMPT_DIR = "service/implementation"

# Matches the "select up to 3" instruction in recommend_task_prompt.txt — kept in
# code as a hard cap since the model is not trusted to obey it on its own.
MAX_RECOMMENDATIONS = 3


class LLMUnavailableError(Exception):
    pass


class NoteNotFoundError(Exception):
    pass


def _call_llm(system_prompt, user_prompt):
    try:
        return ask_llm(system_prompt, user_prompt)
    except requests.exceptions.RequestException as error:
        raise LLMUnavailableError(str(error)) from error


def _fetch_note(note_id):
    status_code, body = get_note(note_id)
    if status_code == 404:
        raise NoteNotFoundError(f"note {note_id} not found")
    if status_code >= 400:
        raise RuntimeError(body.get("error", "database service error"))
    return body


def _extract_keywords(text, limit):
    words = [word.lower() for word in WORD_RE.findall(text)]
    filtered = [word for word in words if word not in STOPWORDS and len(word) > 2]
    counts = Counter(filtered)
    return [word for word, _ in counts.most_common(limit)]


def summarise_note(note_id):
    note = _fetch_note(note_id)
    content = note["note_content"]
    title = note["note_title"]

    skip_threshold = int(get_cfg("SUMMARY_SKIP_THRESHOLD_CHARS", 200))
    chunk_threshold = int(get_cfg("SUMMARY_CHUNK_THRESHOLD_CHARS", 4000))
    length = len(content)

    trace = {"operation": "summarise", "note_id": note_id}

    if length < skip_threshold:
        trace["plan"] = {
            "note_length_chars": length,
            "skip_threshold": skip_threshold,
            "chunk_threshold": chunk_threshold,
            "strategy": "skip_llm",
            "reasoning": (
                f"Note length {length} is below the skip threshold {skip_threshold}; "
                "returning the original text unchanged."
            ),
        }
        trace["act"] = {
            "llm_invoked": False,
            "model": None,
            "chunks_processed": 0,
            "prompt_files": [],
        }
        trace["observe"] = {
            "output_empty": False,
            "output_is_echo": True,
            "output_shorter_than_input": False,
            "output_length_chars": length,
        }
        trace["adapt"] = {
            "action": "none",
            "retry_count": 0,
            "reasoning": "Note too short to summarise; original text returned as-is.",
        }
        return {"summary": content, "trace": trace}

    strategy = "chunked" if length > chunk_threshold else "direct_single_pass"
    trace["plan"] = {
        "note_length_chars": length,
        "skip_threshold": skip_threshold,
        "chunk_threshold": chunk_threshold,
        "strategy": strategy,
        "reasoning": (
            f"Note length {length} exceeds the chunk threshold {chunk_threshold}; "
            "summarising in chunks."
            if strategy == "chunked"
            else f"Note length {length} is between skip and chunk thresholds; "
            "using direct single-pass summarization."
        ),
    }

    system_prompt = load_prompt(f"{PROMPT_DIR}/system_prompt.txt")
    context_prompt = load_prompt(f"{PROMPT_DIR}/context_prompt.txt")

    def run_summary_pass(task_content):
        task_prompt = render_prompt(
            f"{PROMPT_DIR}/summarise_task_prompt.txt",
            note_title=title,
            note_content=task_content,
        )
        user_prompt = f"{task_prompt}\n\n{context_prompt}"
        return _call_llm(system_prompt, user_prompt)

    if strategy == "chunked":
        chunk_size = chunk_threshold // 2
        chunks = [content[i:i + chunk_size] for i in range(0, len(content), chunk_size)]
        chunk_summaries = [run_summary_pass(chunk) for chunk in chunks]
        output = run_summary_pass("\n".join(chunk_summaries))
        chunks_processed = len(chunks)
    else:
        output = run_summary_pass(content)
        chunks_processed = 1

    trace["act"] = {
        "llm_invoked": True,
        "model": OLLAMA_MODEL,
        "chunks_processed": chunks_processed,
        "prompt_files": [
            f"{PROMPT_DIR}/summarise_task_prompt.txt",
            f"{PROMPT_DIR}/context_prompt.txt",
        ],
    }

    output = (output or "").strip()
    output_empty = len(output) == 0
    output_is_echo = output == content.strip()
    output_shorter = len(output) < length

    trace["observe"] = {
        "output_empty": output_empty,
        "output_is_echo": output_is_echo,
        "output_shorter_than_input": output_shorter,
        "output_length_chars": len(output),
    }

    adapt_action = "none"
    retry_count = 0
    adapt_reasoning = "Output passed all checks; accepted as-is."

    if output_empty:
        retry_prompt = render_prompt(
            f"{PROMPT_DIR}/summarise_retry_prompt.txt",
            note_title=title,
            note_content=content,
        )
        user_prompt = f"{retry_prompt}\n\n{context_prompt}"
        output = (_call_llm(system_prompt, user_prompt) or "").strip()
        retry_count = 1
        adapt_action = "retried_with_stricter_prompt"
        adapt_reasoning = "Initial output was empty; retried with a stricter prompt."
        trace["observe"]["output_length_chars"] = len(output)
        trace["observe"]["output_empty"] = len(output) == 0
    elif not output_shorter:
        output = output[:max(1, length // 2)]
        adapt_action = "truncated"
        adapt_reasoning = "Output was not shorter than the input; truncated to half the input length."
        trace["observe"]["output_length_chars"] = len(output)

    trace["adapt"] = {
        "action": adapt_action,
        "retry_count": retry_count,
        "reasoning": adapt_reasoning,
    }

    return {"summary": output, "trace": trace}


def _keyword_overlap_score(source_keywords, candidates):
    source_set = set(source_keywords)
    scored = []
    for candidate in candidates:
        candidate_keywords = set(_extract_keywords(
            f"{candidate['note_title']} {candidate['note_content']}", 20
        ))
        overlap = source_set & candidate_keywords
        if overlap:
            scored.append((len(overlap), {
                "note_id": candidate["note_id"],
                "note_title": candidate["note_title"],
                "notebook_id": candidate["notebook_id"],
                "reason": f"Keyword overlap: {', '.join(sorted(overlap))}",
            }))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored]


def recommend_notes(note_id):
    note = _fetch_note(note_id)
    source_title = note["note_title"]
    source_content = note["note_content"]

    keyword_limit = int(get_cfg("RECOMMEND_KEYWORD_LIMIT", 5))
    candidate_limit = int(get_cfg("RECOMMEND_CANDIDATE_LIMIT", 8))
    context_chars = int(get_cfg("RECOMMEND_CONTEXT_CHARS", 200))

    keywords = _extract_keywords(f"{source_title} {source_content}", keyword_limit)

    trace = {"operation": "recommend", "note_id": note_id}

    candidates_by_id = {}
    for keyword in keywords:
        status_code, body = search_notes(q=keyword)
        if status_code == 200:
            for candidate in body:
                if candidate["note_id"] != note_id:
                    candidates_by_id[candidate["note_id"]] = candidate

    candidates = list(candidates_by_id.values())[:candidate_limit]

    trace["plan"] = {
        "extracted_keywords": keywords,
        "candidate_limit": candidate_limit,
        "candidates_found": len(candidates),
        "reasoning": (
            f"Extracted top {keyword_limit} keywords by frequency (stopwords "
            "removed), searched the database service per keyword, merged and "
            "deduplicated results by note_id, excluded the source note, and capped "
            "candidates at the limit."
        ),
    }

    if not candidates:
        trace["act"] = {
            "llm_invoked": False,
            "candidate_note_ids_sent": [],
            "context_chars_per_candidate": context_chars,
            "prompt_files": [],
        }
        trace["observe"] = {
            "llm_returned_titles": [],
            "hallucinated_titles": [],
            "hallucination_detected": False,
        }
        trace["adapt"] = {
            "action": "none",
            "reasoning": "No candidates found from keyword search; returning an empty list.",
        }
        return {"recommendations": [], "trace": trace}

    system_prompt = load_prompt(f"{PROMPT_DIR}/system_prompt.txt")
    context_prompt = load_prompt(f"{PROMPT_DIR}/context_prompt.txt")

    candidates_text = "\n".join(
        f"- {candidate['note_title']}: {candidate['note_content'][:context_chars]}"
        for candidate in candidates
    )
    task_prompt = render_prompt(
        f"{PROMPT_DIR}/recommend_task_prompt.txt",
        source_title=source_title,
        source_content=source_content[:context_chars],
        candidates=candidates_text,
    )
    user_prompt = f"{task_prompt}\n\n{context_prompt}"
    output = _call_llm(system_prompt, user_prompt)

    trace["act"] = {
        "llm_invoked": True,
        "candidate_note_ids_sent": [candidate["note_id"] for candidate in candidates],
        "context_chars_per_candidate": context_chars,
        "prompt_files": [
            f"{PROMPT_DIR}/recommend_task_prompt.txt",
            f"{PROMPT_DIR}/context_prompt.txt",
        ],
    }

    returned_titles = [
        line.strip("-* \t") for line in (output or "").splitlines() if line.strip()
    ]
    candidate_titles = {candidate["note_title"] for candidate in candidates}
    hallucinated = [title for title in returned_titles if title not in candidate_titles]
    hallucination_detected = len(hallucinated) > 0

    trace["observe"] = {
        "llm_returned_titles": returned_titles,
        "hallucinated_titles": hallucinated,
        "hallucination_detected": hallucination_detected,
    }

    if hallucination_detected or not returned_titles:
        recommendations = _keyword_overlap_score(keywords, candidates)[:MAX_RECOMMENDATIONS]
        trace["adapt"] = {
            "action": "fallback_keyword_overlap",
            "reasoning": (
                "LLM output was empty or contained a title not present in the "
                "candidate set; discarded and fell back to deterministic "
                "keyword-overlap scoring."
            ),
        }
    else:
        title_to_candidate = {candidate["note_title"]: candidate for candidate in candidates}
        recommendations = [
            {
                "note_id": title_to_candidate[title]["note_id"],
                "note_title": title,
                "notebook_id": title_to_candidate[title]["notebook_id"],
                "reason": f"Selected by AI as related to {source_title}",
            }
            for title in returned_titles
            if title in title_to_candidate
        ]
        # The prompt asks the model to select "up to 3", but a small model like
        # qwen2.5:0.5b does not reliably obey that instruction — enforce the cap
        # in code rather than trusting the model to self-limit.
        over_limit = len(recommendations) > MAX_RECOMMENDATIONS
        recommendations = recommendations[:MAX_RECOMMENDATIONS]
        trace["adapt"] = {
            "action": "truncated_to_max_recommendations" if over_limit else "none",
            "reasoning": (
                f"LLM returned more than {MAX_RECOMMENDATIONS} matching titles; "
                "truncated to the cap instead of trusting the model to self-limit."
                if over_limit
                else "All LLM-returned titles matched the candidate set; accepted LLM ranking."
            ),
        }

    return {"recommendations": recommendations, "trace": trace}
