import json

from coordinator import run_workflow, submit_human_review


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

    print("Starting Multi-Agent Workflow...")

    workflow = run_workflow(request, evidence)

    print(json.dumps(workflow, indent=2))

    if workflow["status"] != "awaiting_human_review":
        print("Workflow failed. Human review unavailable.")
        return

    print("\nHuman Review Required")
    print("1. Approve")
    print("2. Partially Accept")
    print("3. Reject")

    choices = {
        "1": "approved",
        "2": "partially_accepted",
        "3": "rejected",
    }

    choice = input("Enter decision (1-3): ").strip()

    if choice not in choices:
        print("Invalid choice. Workflow remains pending.")
        return

    comments = input("Enter review comments: ").strip()

    result, error = submit_human_review(
        workflow["workflow_id"],
        choices[choice],
        comments,
    )

    if error:
        print(f"Human review failed: {error}")
        return

    print("\nFinal Workflow:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
