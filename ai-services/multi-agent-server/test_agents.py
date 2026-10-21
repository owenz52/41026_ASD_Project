import json

from agents.planner_agent import plan_workflow
from agents.worker_agent import execute_workflow
from agents.reviewer_agent import review_workflow


def main():
    evidence = {
        "assignments": [
            {
                "id": 1,
                "title": "Architecture Report",
                "due_date": "2026-10-23",
                "status": "incomplete",
            },
            {
                "id": 2,
                "title": "Cloud Deployment",
                "due_date": "2026-10-28",
                "status": "incomplete",
            },
        ]
    }

    request = "Identify my most urgent upcoming assessments"

    print("Running Planner Agent...", flush=True)
    planner = plan_workflow(request, evidence)

    print("Running Worker Agent...", flush=True)
    worker = execute_workflow(request, planner, evidence)

    print("Running Reviewer Agent...", flush=True)
    reviewer = review_workflow(
        request,
        planner,
        worker,
        evidence,
    )

    print(json.dumps({
        "planner": planner,
        "worker": worker,
        "reviewer": reviewer,
    }, indent=2))


if __name__ == "__main__":
    main()
