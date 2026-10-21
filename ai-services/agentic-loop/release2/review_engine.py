import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from llm_client import OLLAMA_BASE_URL, OLLAMA_MODEL


BASE_DIR = Path(__file__).resolve().parents[1]
REPORTS_DIR = BASE_DIR / "reports" / "release2"
VALIDATION_LOG = REPORTS_DIR / "validation_log.jsonl"

VALID_MODES = {
    "multi_agent",
    "testing",
    "deployment",
}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def validate_sections(review):
    required = [
        "## PLAN",
        "## ACT",
        "## OBSERVE",
        "## ADAPT",
    ]

    text = review.upper()

    return all(section in text for section in required)


def generate_review(mode, evidence, instructions):
    if mode not in VALID_MODES:
        raise ValueError(f"Unsupported review mode: {mode}")

    if not isinstance(evidence, (dict, list)):
        raise ValueError("Evidence must be an object or array")

    if not evidence:
        raise ValueError("Review evidence cannot be empty")

    prompt = f"""
You are an evidence-based Release 2 software reviewer.

Review Mode: {mode}

Review Instructions:
{instructions}

Use only the supplied evidence.
The supplied validation results are authoritative for check status.

Never change a check from pass to fail or fail to pass.
Do not infer that a check executed merely because a status was supplied.
A reported pass or fail is not independently verified execution evidence.

Do not generate replacement JSON evidence.
Do not invent file paths, package names, errors, or test executions.
Do not invent test results or deployment outcomes.
Do not claim something passed without supporting evidence.
Identify missing evidence explicitly.

Keep the entire review under 300 words.
Be concise and avoid repeating recommendations.
Never claim an action was performed unless the evidence proves it.
Review the actual workflow coordination and findings, not the
original user's task as if you were executing it.

Return exactly these Markdown sections:

## PLAN
Describe what needs to be reviewed.

## ACT
Describe the evidence examined.

## OBSERVE
Identify confirmed findings and missing evidence.

## ADAPT
Recommend corrective actions or the next validation step.

EVIDENCE:
{json.dumps(evidence, indent=2)}
"""

    
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": 500,
                # Multi-agent evidence embeds every agent's full output, which
                # can exceed Ollama's default context and silently truncate
                # the review instructions.
                "num_ctx": int(os.getenv("REVIEW_NUM_CTX", "8192")),
                "temperature": 0.1,
                "repeat_penalty": 1.2,
            },
        },
        timeout=120,
    )

    response.raise_for_status()
    review = response.json().get("response", "").strip()
    
    if response.json().get("done_reason") == "length":
        raise RuntimeError(
            "AI review was truncated by the output token limit."
        )


    if not review:
        raise RuntimeError("AI returned an empty review")

    if not validate_sections(review):
        raise RuntimeError(
            "Review does not contain the required sections"
        )

    return review


def save_review(mode, evidence, review):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    generated_at = timestamp()

    filename = (
        f"{mode}-review-"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S%f')}.md"
    )

    report_path = REPORTS_DIR / filename

    content = (
        f"# Release 2 {mode.replace('_', ' ').title()} Review\n\n"
        f"Generated: {generated_at}\n\n"
        f"## Evidence\n\n"
        f"```json\n{json.dumps(evidence, indent=2)}\n```\n\n"
        f"## Review Results\n\n"
        f"{review}\n"
    )

    report_path.write_text(content, encoding="utf-8")

    return report_path


def append_validation_log(entry):
    """Append one review outcome to the persistent validation log."""

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with VALIDATION_LOG.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry) + "\n")


def execute_review(mode, evidence, instructions, validation=None):
    """Generate, save and log a review.

    The deterministic validation result is logged even when the AI review
    fails, so a failed or truncated LLM call never loses the evidence outcome.
    """

    entry = {
        "timestamp": timestamp(),
        "mode": mode,
        "evidence_source": (
            evidence.get("source") if isinstance(evidence, dict) else None
        ),
        "validation": validation,
    }

    try:
        review = generate_review(mode, evidence, instructions)
    except Exception as exc:
        entry["review_status"] = "failed"
        entry["error"] = str(exc)
        append_validation_log(entry)
        raise

    report_path = save_review(mode, evidence, review)

    entry["review_status"] = "completed"
    entry["report"] = str(report_path)
    append_validation_log(entry)

    return {
        "status": "completed",
        "mode": mode,
        "generated_at": timestamp(),
        "review": review,
        "report": str(report_path),
        "validation_log": str(VALIDATION_LOG),
    }
