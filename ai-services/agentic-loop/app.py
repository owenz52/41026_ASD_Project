import asyncio
import os
import threading
import time

from flask import Flask, jsonify

from review_service import review_new_ci_runs
from service_checks import check_mcp, check_rag, check_shared_services


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


if __name__ == "__main__":
    thread = threading.Thread(target=polling_loop, daemon=True)
    thread.start()
    app.run(host="0.0.0.0", port=5012)