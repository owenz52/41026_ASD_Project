from .review_engine import execute_review


REQUIRED_CHECKS = {
    "build",
    "deployment",
    "health",
    "security",
}


def validate_deployment_evidence(evidence):
    """Validate the reported cloud deployment checks."""

    if not isinstance(evidence, dict):
        raise ValueError("Deployment evidence must be a JSON object")

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


def review_deployment(evidence):
    validation = validate_deployment_evidence(evidence)

    review_evidence = {
        "deployment": evidence,
        "validation": validation,
    }

    instructions = """
Review Azure cloud deployment evidence.

Assess:
- Whether the application build succeeded.
- Whether Azure deployment completed successfully.
- Whether the deployed application passed its health checks.
- Whether security controls were validated.
- Any failed or missing deployment evidence.
- Whether the supplied results support release readiness.

Do not assume a deployment succeeded because a build passed.
Do not invent Azure resources, endpoints or test results.
Do not approve deployment readiness when required checks fail.

Distinguish between confirmed results and missing evidence.
Recommend corrective actions for failures and missing checks.
"""

    result = execute_review(
        mode="deployment",
        evidence=review_evidence,
        instructions=instructions,
    )

    result["validation"] = validation

    return result
