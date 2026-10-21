
import os

from flask import Flask, jsonify, request

from coordinator import (
    get_workflow,
    run_workflow,
    submit_human_review,
)


app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "shared-multi-agent-server",
    })


@app.post("/workflows")
def start_workflow():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    user_request = data.get("request", "")
    evidence = data.get("evidence", {})

    if not isinstance(user_request, str) or not user_request.strip():
        return jsonify({
            "error": "A non-empty request is required"
        }), 400

    if not isinstance(evidence, (dict, list)):
        return jsonify({
            "error": "Evidence must be a JSON object or array"
        }), 400

    result = run_workflow(user_request, evidence)

    return jsonify(result), (
        200 if result["status"] == "awaiting_human_review"
        else 503
    )


@app.get("/workflows/<workflow_id>")
def workflow_status(workflow_id):
    workflow = get_workflow(workflow_id)

    if workflow is None:
        return jsonify({"error": "Workflow not found"}), 404

    return jsonify(workflow)


@app.post("/workflows/<workflow_id>/decision")
def human_decision(workflow_id):
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    result, error = submit_human_review(
        workflow_id,
        data.get("decision"),
        data.get("comments", ""),
    )

    if error:
        status_code = 404 if error == "Workflow not found" else 400
        return jsonify({"error": error}), status_code

    return jsonify(result)


if __name__ == "__main__":
    app.run(
        host=os.getenv("MULTI_AGENT_HOST", "127.0.0.1"),
        port=int(os.getenv("MULTI_AGENT_PORT", "5013")),
        debug=False,
    )
