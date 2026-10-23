
"use strict";

// Same-origin API endpoint.
// We will configure Nginx to proxy this path later.
const MULTI_AGENT_API = "/multi-agent-api";

let currentWorkflowId = null;

function setMessage(message, isError = false) {
    const element = document.getElementById("workflow-message");

    element.textContent = message;
    element.style.color = isError ? "#dc2626" : "";
}

function readUser() {
    try {
        const raw = localStorage.getItem("user");
        return raw ? JSON.parse(raw) : null;
    } catch {
        return null;
    }
}

function initialiseUser() {
    const user = readUser();

    if (!user) {
        window.location.href = "/login.html";
        return;
    }

    document.getElementById("user-name").textContent =
        user.name || user.email || "Student";

    document.getElementById("auth-action")
        .addEventListener("click", () => {
            localStorage.removeItem("user");
            window.location.href = "/login.html";
        });
}

async function apiRequest(path, options = {}) {
    const response = await fetch(
        `${MULTI_AGENT_API}${path}`,
        {
            ...options,
            headers: {
                "Content-Type": "application/json",
                ...(options.headers || {})
            }
        }
    );

    let data;

    try {
        data = await response.json();
    } catch {
        throw new Error("The server returned invalid JSON.");
    }

    if (!response.ok) {
        throw new Error(
            data.error || `HTTP error ${response.status}`
        );
    }

    return data;
}

function displayWorkflow(workflow) {
    currentWorkflowId = workflow.workflow_id;

    document.getElementById("workflow-results").hidden = false;

    document.getElementById("workflow-id").textContent =
        workflow.workflow_id || "";

    document.getElementById("workflow-status").textContent =
        workflow.status || "unknown";

    document.getElementById("planner-output").textContent =
        workflow.planner?.plan || "No Planner output";

    document.getElementById("worker-output").textContent =
        workflow.worker?.output || "No Worker output";

    document.getElementById("reviewer-output").textContent =
        workflow.reviewer?.review || "No Reviewer output";

    const awaitingReview =
        workflow.status === "awaiting_human_review";

    document.getElementById("human-review").hidden =
        !awaitingReview;

    document.getElementById("lookup-id").value =
        workflow.workflow_id || "";

    if (workflow.human_review) {
        setMessage(
            `Human Review: ${workflow.human_review.decision}`
        );
    }
}

async function startWorkflow() {
    const button = document.getElementById("start-workflow");

    const userRequest = document
        .getElementById("workflow-request")
        .value.trim();

    const evidenceText = document
        .getElementById("workflow-evidence")
        .value.trim();

    if (!userRequest) {
        setMessage("Please enter a workflow request.", true);
        return;
    }

    let evidence;

    try {
        evidence = evidenceText
            ? JSON.parse(evidenceText)
            : {};
    } catch {
        setMessage("Evidence must contain valid JSON.", true);
        return;
    }

    if (
        !Array.isArray(evidence) &&
        (
            typeof evidence !== "object" ||
            evidence === null
        )
    ) {
        setMessage("Evidence must be a JSON object or array.", true);
        return;
    }

    button.disabled = true;
    setMessage("Running Planner, Worker and Reviewer...");

    try {
        const workflow = await apiRequest(
            "/workflows",
            {
                method: "POST",
                body: JSON.stringify({
                    request: userRequest,
                    evidence: evidence
                })
            }
        );

        displayWorkflow(workflow);

        setMessage(
            "Workflow completed. Review the agent outputs."
        );

    } catch (error) {
        setMessage(error.message, true);
    } finally {
        button.disabled = false;
    }
}

async function submitReview() {
    if (!currentWorkflowId) {
        setMessage("No workflow has been selected.", true);
        return;
    }

    const decision = document
        .getElementById("review-decision")
        .value;

    const comments = document
        .getElementById("review-comments")
        .value.trim();

    const button = document.getElementById("submit-review");

    button.disabled = true;
    setMessage("Submitting Human Review...");

    try {
        const workflow = await apiRequest(
            `/workflows/${encodeURIComponent(currentWorkflowId)}/decision`,
            {
                method: "POST",
                body: JSON.stringify({
                    decision,
                    comments
                })
            }
        );

        displayWorkflow(workflow);

        setMessage(
            `Human Review recorded: ${workflow.status}`
        );

    } catch (error) {
        setMessage(error.message, true);
    } finally {
        button.disabled = false;
    }
}


async function lookupWorkflow() {
    const workflowId = document
        .getElementById("lookup-id")
        .value.trim();

    const message = document.getElementById("lookup-message");
    const button = document.getElementById("lookup-workflow");

    if (!workflowId) {
        message.textContent = "Please enter a workflow ID.";
        return;
    }

    button.disabled = true;
    message.textContent = "Retrieving workflow...";

    try {
        const workflow = await apiRequest(
            `/workflows/${encodeURIComponent(workflowId)}`
        );

        displayWorkflow(workflow);

        message.textContent =
            `Workflow retrieved successfully. Status: ${workflow.status}`;

        document.getElementById("workflow-results")
            .scrollIntoView({
                behavior: "smooth",
                block: "start"
            });

    } catch (error) {
        message.textContent = `Error: ${error.message}`;
    } finally {
        button.disabled = false;
    }
}


document.addEventListener("DOMContentLoaded", () => {
    initialiseUser();

    document.getElementById("start-workflow")
        .addEventListener("click", startWorkflow);

    document.getElementById("submit-review")
        .addEventListener("click", submitReview);

    document.getElementById("lookup-workflow")
        .addEventListener("click", lookupWorkflow);
});
