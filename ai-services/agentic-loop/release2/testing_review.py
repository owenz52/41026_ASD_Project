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
    }


def review_testing(evidence):
    validation = validate_testing_evidence(evidence)

    review_evidence = {
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
    )

    result["validation"] = validation

    return result
