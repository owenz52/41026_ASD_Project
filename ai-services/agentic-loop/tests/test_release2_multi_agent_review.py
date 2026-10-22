from release2.multi_agent_review import validate_workflow_evidence


FULL_EVENTS = [
    "workflow_started",
    "planner_completed",
    "worker_completed",
    "reviewer_completed",
    "human_review_completed",
]


def evidence(decision="approved", events=FULL_EVENTS, status=None, **agents):
    workflow = {
        "planner": {"plan": "p"},
        "worker": {"output": "w"},
        "reviewer": {"review": "r"},
        "human_review": {"decision": decision} if decision else None,
        "status": status or decision or "awaiting_human_review",
    }
    workflow.update(agents)
    return {
        "workflow": workflow,
        "audit_events": [{"event": name} for name in events],
    }


def test_approved_workflow_passes():
    assert validate_workflow_evidence(evidence())["status"] == "pass"


def test_rejected_workflow_is_still_a_valid_workflow():
    result = validate_workflow_evidence(evidence("rejected"))

    assert result["status"] == "pass"


def test_missing_human_review_fails():
    result = validate_workflow_evidence(
        evidence(decision=None, events=FULL_EVENTS[:-1])
    )

    assert result["status"] == "fail"
    assert result["missing_events"] == ["human_review_completed"]
    assert result["checks"]["human_review_present"] is False


def test_failed_worker_fails():
    result = validate_workflow_evidence(evidence(
        decision=None,
        events=["workflow_started", "planner_completed", "workflow_failed"],
        status="failed",
        worker=None,
        reviewer=None,
    ))

    assert result["status"] == "fail"
    assert result["checks"]["worker_present"] is False
    assert "reviewer_completed" in result["missing_events"]


def test_out_of_order_events_fail():
    events = [FULL_EVENTS[0], FULL_EVENTS[2], FULL_EVENTS[1], *FULL_EVENTS[3:]]

    result = validate_workflow_evidence(evidence(events=events))

    assert result["checks"]["correct_event_order"] is False


def test_status_not_matching_decision_fails():
    result = validate_workflow_evidence(evidence(status="approved_by_mistake"))

    assert result["checks"]["final_status_matches_decision"] is False
