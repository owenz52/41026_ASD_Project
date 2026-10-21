import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
import logging
from agents.planner_agent import plan_workflow
from agents.worker_agent import execute_workflow
from agents.reviewer_agent import review_workflow

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"

HISTORY_FILE = LOG_DIR / "workflow_history.jsonl"
AUDIT_FILE = LOG_DIR / "coordination_audit.jsonl"

LOCK = threading.RLock()
WORKFLOWS = {}

def load_workflows():
    """
    Restore the latest saved state of each workflow
    from the workflow history log.
    """
    if not HISTORY_FILE.exists():
        return

    with LOCK:
        with HISTORY_FILE.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue

                try:
                    workflow = json.loads(line)
                except json.JSONDecodeError as exc:
                    logger.warning(
                        "Skipping malformed workflow history record: %s",
                        exc,
                    )
                    continue

                workflow_id = workflow.get("workflow_id")

                if not workflow_id:
                    continue

                WORKFLOWS[workflow_id] = workflow

def timestamp():
    return datetime.now(timezone.utc).isoformat()


def write_log(path, data):
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(data) + "\n")


def record_event(workflow_id, event, details=None):
    write_log(AUDIT_FILE, {
        "timestamp": timestamp(),
        "workflow_id": workflow_id,
        "event": event,
        "details": details or {},
    })


def save_workflow(workflow):
    write_log(HISTORY_FILE, workflow)


def run_workflow(user_request, evidence):
    workflow_id = str(uuid.uuid4())

    workflow = {
        "workflow_id": workflow_id,
        "created_at": timestamp(),
        "request": user_request,
        "evidence": evidence,
        "status": "running",
        "planner": None,
        "worker": None,
        "reviewer": None,
        "human_review": None,
    }

    with LOCK:
        WORKFLOWS[workflow_id] = workflow

    record_event(workflow_id, "workflow_started")

    try:
        planner = plan_workflow(user_request, evidence)
        workflow["planner"] = planner

        record_event(
            workflow_id,
            "planner_completed",
            {"model": planner["model"]},
        )

        worker = execute_workflow(
            user_request,
            planner,
            evidence,
        )
        workflow["worker"] = worker

        record_event(
            workflow_id,
            "worker_completed",
            {"model": worker["model"]},
        )

        reviewer = review_workflow(
            user_request,
            planner,
            worker,
            evidence,
        )
        workflow["reviewer"] = reviewer

        record_event(
            workflow_id,
            "reviewer_completed",
            {"model": reviewer["model"]},
        )

        workflow["status"] = "awaiting_human_review"

    except Exception as exc:
        workflow["status"] = "failed"
        workflow["error"] = str(exc)

        record_event(
            workflow_id,
            "workflow_failed",
            {"error": str(exc)},
        )

    workflow["updated_at"] = timestamp()

    with LOCK:
        save_workflow(workflow)

    return workflow


VALID_DECISIONS = {
    "approved",
    "partially_accepted",
    "rejected",
}


def submit_human_review(workflow_id, decision, comments=""):
    with LOCK:
        workflow = WORKFLOWS.get(workflow_id)

        if workflow is None:
            return None, "Workflow not found"

        if workflow["status"] != "awaiting_human_review":
            return None, "Workflow is not awaiting human review"

        if decision not in VALID_DECISIONS:
            return None, "Invalid decision"

        workflow["human_review"] = {
            "decision": decision,
            "comments": comments,
            "reviewed_at": timestamp(),
        }

        workflow["status"] = decision
        workflow["updated_at"] = timestamp()

        record_event(
            workflow_id,
            "human_review_completed",
            workflow["human_review"],
        )

        save_workflow(workflow)

        return workflow, None


def get_workflow(workflow_id):
    with LOCK:
        return WORKFLOWS.get(workflow_id)
load_workflows()