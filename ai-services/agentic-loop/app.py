import asyncio
import os
import threading
import time

from flask import Flask, jsonify, request

from review_service import review_new_ci_runs
from service_checks import check_mcp, check_rag, check_shared_services
from release2.multi_agent_review import review_multi_agent_workflow
from release2.testing_review import review_testing
from release2.deployment_review import review_deployment


app = Flask(__name__)

POLL_SECONDS = int(os.getenv("POLL_SECONDS", "300"))

status = {
    "last_check": None,
    "last_result": "not yet checked",
    "service_checks": None,
}


def polling_loop():
    while True:
        try:
            status["service_checks"] = check_shared_services()
            reports = review_new_ci_runs()

            if reports:
                status["last_result"] = f"{len(reports)} review(s) generated"
            else:
                status["last_result"] = "No new CI runs required review"

        except Exception as error:
            status["last_result"] = f"Error: {error}"

        status["last_check"] = time.strftime("%Y-%m-%d %H:%M:%S")
        time.sleep(POLL_SECONDS)


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "shared-agentic-loop",
        "poll_seconds": POLL_SECONDS,
        "last_check": status["last_check"],
        "last_result": status["last_result"],
        "service_checks": status["service_checks"],
    })

@app.post("/validate-mcp")
def validate_mcp():
    try:
        result = asyncio.run(check_mcp())
    except Exception as exc:
        result = {"status": "fail", "error": str(exc)}

    return jsonify({"mode": "mcp", **result}), (
        200 if result["status"] == "pass" else 503
    )


@app.post("/validate-rag")
def validate_rag():
    try:
        result = check_rag()
    except Exception as exc:
        result = {"status": "fail", "error": str(exc)}

    return jsonify({"mode": "rag", **result}), (
        200 if result["status"] == "pass" else 503
    )

@app.post("/validate-now")
def validate_now():
    result = check_shared_services()
    status["service_checks"] = result
    return jsonify(result), (200 if result["status"] == "pass" else 503)


@app.post("/review-now")
def review_now():
    reports = review_new_ci_runs()
    return jsonify({
        "reviewed": len(reports),
        "reports": [report.name for report in reports],
    })


@app.post("/review-multi-agent")
def review_multi_agent():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    workflow_id = data.get("workflow_id")

    if not isinstance(workflow_id, str) or not workflow_id.strip():
        return jsonify({"error": "workflow_id is required"}), 400

    try:
        result = review_multi_agent_workflow(workflow_id)
        return jsonify(result), 200
    except (ValueError, FileNotFoundError) as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        app.logger.exception("Multi-Agent review failed")
        return jsonify({"error": "Review failed"}), 500


@app.post("/review-testing")
def review_testing_endpoint():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    try:
        result = review_testing(data)
        return jsonify(result), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        app.logger.exception("Testing review failed")
        return jsonify({"error": "Review failed"}), 500


@app.post("/review-deployment")
def review_deployment_endpoint():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    try:
        result = review_deployment(data)
        return jsonify(result), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        app.logger.exception("Deployment review failed")
        return jsonify({"error": "Review failed"}), 500


if __name__ == "__main__":
    thread = threading.Thread(target=polling_loop, daemon=True)
    thread.start()
    app.run(host="0.0.0.0", port=5012)