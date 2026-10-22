from .evidence_collectors import collect_testing_evidence
from .review_engine import execute_review


REQUIRED_CHECKS = {
    "ruff",
    "detect_secrets",
    "pip_audit",
    "pytest",
}


def validate_testing_evidence(evidence):
    """Validate supplied pre-commit and post-commit test results."""

    if not isinstance(evidence, dict):
        raise ValueError("Testing evidence must be a JSON object")

    results = evidence.get("checks")

    if not isinstance(results, dict):
        raise ValueError("Evidence must contain a checks object")

    missing = sorted(REQUIRED_CHECKS - results.keys())

    checks = {}

    for name in REQUIRED_CHECKS:
        check = results.get(name)

        checks[name] = (
            isinstance(check, dict)
            and check.get("status") == "pass"
        )

    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "missing_checks": missing,
        "evidence_source": evidence.get("source", "supplied"),
    }


def review_testing(evidence=None, workflows=None, branch="main"):
    """Review testing evidence.

    With no evidence supplied, the pre-commit hooks are executed and the
    post-commit GitHub Actions endpoint tests are collected. Supplied evidence
    is still accepted but is labelled as supplied rather than collected.
    """

    if evidence is None:
        evidence = collect_testing_evidence(workflows=workflows, branch=branch)
    else:
        evidence = {**evidence, "source": evidence.get("source", "supplied")}

    validation = validate_testing_evidence(evidence)

    review_evidence = {
        "source": evidence["source"],
        "testing": evidence,
        "validation": validation,
    }

    instructions = """
Review software testing and security scan evidence.

Assess:
- Ruff linting and security checks.
- detect-secrets scanning.
- pip-audit dependency vulnerability checks.
- pytest automated tests.
- Any failed or missing checks.
- Whether the supplied evidence supports release readiness.

Do not invent test executions or claim that missing checks passed.

If the evidence source is "collected", the checks were executed by the
agentic loop: pre-commit hooks were run locally and endpoint tests were read
from GitHub Actions. If the source is "supplied", say that the results were
reported to the loop and were not independently executed.
For pytest, report which student workflows passed, failed or had no
endpoint test evidence.

Distinguish between:
1. Checks that were executed and passed.
2. Checks that failed.
3. Checks for which no evidence was supplied.

Recommend corrective actions for failures and missing evidence.
"""

    result = execute_review(
        mode="testing",
        evidence=review_evidence,
        instructions=instructions,
        validation=validation,
    )

    result["validation"] = validation

    return result
