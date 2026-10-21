
import json
import os
from pathlib import Path

from .review_engine import execute_review


BASE_DIR = Path(__file__).resolve().parents[2]

MULTI_AGENT_LOG_DIR = Path(
    os.getenv(
        "MULTI_AGENT_LOG_DIR",
        str(BASE_DIR / "multi-agent-server" / "logs"),
    )
)

HISTORY_FILE = MULTI_AGENT_LOG_DIR / "workflow_history.jsonl"
AUDIT_FILE = MULTI_AGENT_LOG_DIR / "coordination_audit.jsonl"


def load_jsonl(path):
    """Read JSONL evidence from an existing log file."""

    if not path.is_file():
        raise FileNotFoundError(f"Evidence file not found: {path}")

    records = []

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {line_number} of {path.name}"
                ) from exc

    return records


def collect_workflow_evidence(workflow_id):
    """Retrieve the latest workflow state and its audit events."""

    if not isinstance(workflow_id, str) or not workflow_id.strip():
        raise ValueError("workflow_id is required")

    history = load_jsonl(HISTORY_FILE)
    audit = load_jsonl(AUDIT_FILE)

    matching_history = [
        record
        for record in history
        if record.get("workflow_id") == workflow_id
    ]

    if not matching_history:
        raise ValueError(f"Workflow not found: {workflow_id}")

    workflow = matching_history[-1]

    events = [
        record
        for record in audit
        if record.get("workflow_id") == workflow_id
    ]

    return {
        "workflow": workflow,
        "audit_events": events,
    }


def validate_workflow_evidence(evidence):
    """Perform deterministic validation of workflow coordination."""

    workflow = evidence["workflow"]
    events = evidence["audit_events"]

    event_names = [event.get("event") for event in events]

    required_events = [
        "workflow_started",
        "planner_completed",
        "worker_completed",
        "reviewer_completed",
        "human_review_completed",
    ]

    missing_events = [
        event
        for event in required_events
        if event not in event_names
    ]

    positions = [
        event_names.index(event)
        for event in required_events
        if event in event_names
    ]

    correct_order = (
        not missing_events
        and positions == sorted(positions)
    )

    human_review = workflow.get("human_review")

    valid_decisions = {
        "approved",
        "partially_accepted",
        "rejected",
    }

    decision = (
        human_review.get("decision")
        if isinstance(human_review, dict)
        else None
    )

    checks = {
        "planner_present": bool(workflow.get("planner")),
        "worker_present": bool(workflow.get("worker")),
        "reviewer_present": bool(workflow.get("reviewer")),
        "human_review_present": decision in valid_decisions,
        "audit_events_complete": not missing_events,
        "correct_event_order": correct_order,
        "final_status_matches_decision": workflow.get("status") == decision,
    }

    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "missing_events": missing_events,
    }


def review_multi_agent_workflow(workflow_id):
    evidence = collect_workflow_evidence(workflow_id)

    validation = validate_workflow_evidence(evidence)

    evidence["validation"] = validation

    instructions = """
Review the Planner, Worker, Reviewer and Human Review workflow.

Check:
- Whether all required agents executed.
- Whether workflow events occurred in the correct order.
- Whether the Reviewer identified unsupported claims.
- Whether the human decision is recorded.
- Whether the final status matches the human decision.
- Whether any evidence is missing or contradictory.

Distinguish between:
1. Workflow execution correctness.
2. Quality and accuracy of the generated agent outputs.

A technically complete workflow can still have incorrect AI output.
Do not treat workflow completion as proof of factual accuracy.

Use the deterministic validation results as evidence.
"""

    result = execute_review(
        mode="multi_agent",
        evidence=evidence,
        instructions=instructions,
        validation=validation,
    )

    result["validation"] = validation
    result["workflow_id"] = workflow_id

    return result
