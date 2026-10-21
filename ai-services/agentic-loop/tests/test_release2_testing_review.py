import json
import sys

import pytest

from release2 import evidence_collectors, review_engine, testing_review


def passing(source="pre-commit"):
    return {"status": "pass", "executed": True, "source": source}


def collected(**overrides):
    checks = {
        "ruff": passing(),
        "detect_secrets": passing(),
        "pip_audit": passing(),
        "pytest": passing("github-actions"),
    }
    checks.update(overrides)
    return {"source": "collected", "checks": checks}


# --- deterministic validation -------------------------------------------

def test_all_collected_checks_pass():
    result = testing_review.validate_testing_evidence(collected())

    assert result["status"] == "pass"
    assert result["evidence_source"] == "collected"
    assert result["missing_checks"] == []


def test_failed_hook_fails_validation():
    result = testing_review.validate_testing_evidence(
        collected(detect_secrets={"status": "fail", "executed": True})
    )

    assert result["status"] == "fail"
    assert result["checks"]["detect_secrets"] is False


def test_missing_ci_evidence_fails_validation():
    evidence = collected()
    del evidence["checks"]["pytest"]

    result = testing_review.validate_testing_evidence(evidence)

    assert result["status"] == "fail"
    assert result["missing_checks"] == ["pytest"]


# --- pre-commit execution ------------------------------------------------

def fake_hook(monkeypatch, exit_code, output):
    script = f"import sys; print({output!r}); sys.exit({exit_code})"
    monkeypatch.setattr(
        evidence_collectors,
        "_precommit_command",
        lambda: [sys.executable, "-c", script],
    )


def test_hook_exit_zero_is_pass(monkeypatch):
    fake_hook(monkeypatch, 0, "Ruff....Passed")

    record = evidence_collectors.run_precommit_hook("ruff", "ruff-release2")

    assert record["status"] == "pass"
    assert record["executed"] is True
    assert record["exit_code"] == 0


def test_hook_exit_nonzero_is_fail_with_output(monkeypatch):
    fake_hook(monkeypatch, 1, "Potential secret in config.py")

    record = evidence_collectors.run_precommit_hook(
        "detect_secrets", "detect-secrets"
    )

    assert record["status"] == "fail"
    assert "Potential secret" in record["output"]


def test_missing_precommit_is_not_executed(monkeypatch):
    monkeypatch.setattr(
        evidence_collectors,
        "_precommit_command",
        lambda: ["/nonexistent/pre-commit"],
    )

    record = evidence_collectors.run_precommit_hook("ruff", "ruff-release2")

    assert record["status"] == "error"
    assert record["executed"] is False


# --- GitHub Actions endpoint tests ---------------------------------------

def fake_github(monkeypatch, steps, runs=True):
    def github_get(path, params=None):
        if path.endswith("/runs"):
            data = {"workflow_runs": []}
            if runs:
                data["workflow_runs"] = [{
                    "id": 1,
                    "html_url": "https://github.com/x/y/actions/runs/1",
                    "head_sha": "abc123",
                    "event": "push",
                    "conclusion": "success",
                    "updated_at": "2026-10-21T09:10:28Z",
                }]
            return data, None
        return {"jobs": [{"name": "build", "steps": steps}]}, None

    monkeypatch.setattr(evidence_collectors, "_github_get", github_get)


def step(name, conclusion="success"):
    return {"name": name, "conclusion": conclusion}


def test_endpoint_test_step_success_is_pass(monkeypatch):
    fake_github(monkeypatch, [
        step("Install pytest"),
        step("Test Assessment Tracker endpoints"),
        step("Upload endpoint test evidence"),
    ])

    record = evidence_collectors.collect_workflow_tests("student-a.yml")

    assert record["status"] == "pass"
    assert [s["step"] for s in record["test_steps"]] == [
        "Test Assessment Tracker endpoints"
    ]


def test_endpoint_test_step_failure_is_fail(monkeypatch):
    fake_github(monkeypatch, [
        step("Test Enrolment endpoint functions", "failure"),
    ])

    record = evidence_collectors.collect_workflow_tests("student-b.yml")

    assert record["status"] == "fail"


def test_workflow_without_test_step_is_missing(monkeypatch):
    fake_github(monkeypatch, [step("Build Notebook images")])

    record = evidence_collectors.collect_workflow_tests("student-c.yml")

    assert record["status"] == "missing"
    assert "No endpoint test step" in record["error"]


def test_workflow_without_runs_is_missing(monkeypatch):
    fake_github(monkeypatch, [], runs=False)

    record = evidence_collectors.collect_workflow_tests("student-d.yml")

    assert record["status"] == "missing"


def test_one_missing_workflow_blocks_ci_pass(monkeypatch):
    results = {
        "a.yml": {"status": "pass", "test_steps": [{}]},
        "b.yml": {"status": "missing"},
    }
    monkeypatch.setattr(
        evidence_collectors,
        "collect_workflow_tests",
        lambda workflow, branch: {"workflow": workflow, **results[workflow]},
    )

    aggregate = evidence_collectors.collect_ci_tests(["a.yml", "b.yml"])

    assert aggregate["status"] == "missing"
    assert aggregate["workflows_passing"] == 1


# --- review flow and validation log --------------------------------------

@pytest.fixture
def reports_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(review_engine, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(
        review_engine, "VALIDATION_LOG", tmp_path / "validation_log.jsonl"
    )
    return tmp_path


def read_log(reports_dir):
    lines = (reports_dir / "validation_log.jsonl").read_text().splitlines()
    return [json.loads(line) for line in lines]


REVIEW = "## PLAN\nx\n## ACT\nx\n## OBSERVE\nx\n## ADAPT\nx"


def test_supplied_evidence_is_labelled_supplied(reports_dir, monkeypatch):
    monkeypatch.setattr(
        review_engine, "generate_review", lambda *args: REVIEW
    )

    supplied = collected()
    del supplied["source"]

    result = testing_review.review_testing(supplied)

    assert result["validation"]["evidence_source"] == "supplied"
    assert read_log(reports_dir)[0]["evidence_source"] == "supplied"


def test_no_evidence_triggers_collection(reports_dir, monkeypatch):
    monkeypatch.setattr(
        review_engine, "generate_review", lambda *args: REVIEW
    )
    monkeypatch.setattr(
        testing_review,
        "collect_testing_evidence",
        lambda workflows, branch: collected(),
    )

    result = testing_review.review_testing()

    assert result["validation"]["status"] == "pass"
    log = read_log(reports_dir)
    assert log[0]["review_status"] == "completed"
    assert log[0]["evidence_source"] == "collected"


def test_validation_logged_when_ai_review_fails(reports_dir, monkeypatch):
    def broken(*args):
        raise RuntimeError("AI review was truncated")

    monkeypatch.setattr(review_engine, "generate_review", broken)

    with pytest.raises(RuntimeError):
        testing_review.review_testing(
            collected(pip_audit={"status": "fail", "executed": True})
        )

    entry = read_log(reports_dir)[0]
    assert entry["review_status"] == "failed"
    assert entry["validation"]["status"] == "fail"
    assert entry["validation"]["checks"]["pip_audit"] is False
