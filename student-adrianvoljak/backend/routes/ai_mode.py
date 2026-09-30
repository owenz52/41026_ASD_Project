import json
from datetime import date
from os import getenv

from flask import Blueprint, jsonify, request

from services import database_api
from services.llm_client import ask_llm


ai_mode_bp = Blueprint("ai_mode", __name__)

STATUS_LABELS = {
    "not_started": "Not started",
    "in_progress": "In progress",
    "completed": "Completed",
}


def parse_ranking(raw, assignments):
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("The ranking must be a JSON object")

    ids = data.get("ordered_ids")
    expected = {assignment["assignment_id"] for assignment in assignments}

    if (
        not isinstance(ids, list)
        or any(type(item) is not int for item in ids)
        or len(ids) != len(assignments)
        or len(set(ids)) != len(ids)
        or set(ids) != expected
    ):
        raise ValueError(
            "The ranking must contain every incomplete assignment ID exactly once"
        )

    return ids


def fallback_ranking(assignments):
    ranked = sorted(
        assignments,
        key=lambda assignment: (
            assignment.get("due_date") or "9999-12-31",
            -float(assignment.get("weighting") or 0),
            assignment["assignment_id"],
        ),
    )
    return [assignment["assignment_id"] for assignment in ranked]


def render_recommendation(ordered_ids, assignments, used_fallback):
    records = {
        assignment["assignment_id"]: assignment
        for assignment in assignments
    }

    lines = [
        (
            "The AI ranking failed validation. Fallback: earliest due "
            "date first, then highest weighting."
            if used_fallback
            else "AI suggested priority order. Assessment details come "
                 "directly from your records."
        ),
        "",
    ]

    for position, assignment_id in enumerate(ordered_ids, start=1):
        assignment = records[assignment_id]
        status = STATUS_LABELS.get(
            assignment["status"],
            assignment["status"],
        )
        weighting = assignment.get("weighting")
        weighting_text = (
            f"{weighting}%"
            if weighting is not None
            else "not recorded"
        )

        lines.append(
            f"{position}. {assignment['title']} — "
            f"due {assignment.get('due_date') or 'not recorded'}; "
            f"weighting {weighting_text}; status: {status}."
        )

    first = records[ordered_ids[0]]
    lines.extend([
        "",
        f"NEXT ACTION: Work on {first['title']}, "
        "the first assessment in this suggested order.",
    ])
    return "\n".join(lines)


@ai_mode_bp.post("/ai/prioritise")
def prioritise_assignments():
    if getenv("AI_ENABLED", "true").lower() != "true":
        return jsonify({
            "status": "disabled",
            "message": "AI mode is disabled",
        }), 503

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    student_id = data.get("student_id")
    if type(student_id) is not int or student_id <= 0:
        return jsonify({"error": "student_id must be a positive integer"}), 400

    agent_steps = [{
        "stage": "PLAN",
        "detail": (
            "Ask the AI to rank the student's incomplete assessment IDs "
            "using due dates, weighting and progress."
        ),
    }]

    try:
        status_code, assignments = database_api.get_assignments({
            "student_id": student_id,
            "order": "asc",
        })

        if status_code != 200:
            return jsonify({
                "error": "Could not retrieve assignments",
                "agent_steps": agent_steps,
            }), status_code

        if not isinstance(assignments, list):
            raise RuntimeError("Unexpected assignment response")

        incomplete = [
            assignment
            for assignment in assignments
            if assignment.get("student_id") == student_id
            and assignment["status"] != "completed"
        ]

        agent_steps.append({
            "stage": "ACT",
            "detail": f"Retrieved {len(incomplete)} incomplete assessment(s).",
        })

        if not incomplete:
            agent_steps.extend([
                {
                    "stage": "OBSERVE",
                    "detail": "No incomplete assessments were found.",
                },
                {
                    "stage": "ADAPT",
                    "detail": "No AI prioritisation is required.",
                },
            ])
            return jsonify({
                "message": "There are no incomplete assignments.",
                "agent_steps": agent_steps,
            }), 200

        ids = [assignment["assignment_id"] for assignment in incomplete]
        schema = {
            "type": "object",
            "properties": {
                "ordered_ids": {
                    "type": "array",
                    "items": {"type": "integer", "enum": ids},
                    "minItems": len(ids),
                    "maxItems": len(ids),
                    "uniqueItems": True,
                },
            },
            "required": ["ordered_ids"],
            "additionalProperties": False,
        }

        system_prompt = (
            "You rank university assessments by urgency and importance. "
            "Consider due dates, weighting and current progress. "
            "Return only a JSON object containing ordered_ids. "
            "Include every supplied assignment ID exactly once, "
            "highest priority first."
        )

        records = [{
            key: assignment.get(key)
            for key in (
                "assignment_id",
                "title",
                "due_date",
                "weighting",
                "status",
            )
        } for assignment in incomplete]

        task_prompt = (
            f"Today's date is {date.today().isoformat()}.\n"
            "Rank these incomplete assessments:\n"
            + json.dumps(records)
        )

        raw = ask_llm(system_prompt, task_prompt, schema)
        used_fallback = False

        try:
            ordered_ids = parse_ranking(raw, incomplete)
            agent_steps.append({
                "stage": "OBSERVE",
                "detail": (
                    "The AI returned every incomplete assignment ID "
                    "exactly once. Ranking quality is not automatically verified."
                ),
            })
            agent_steps.append({
                "stage": "ADAPT",
                "detail": "No retry was required.",
            })

        except (ValueError, TypeError):
            agent_steps.append({
                "stage": "OBSERVE",
                "detail": "The first AI ranking failed ID validation.",
            })

            retry_prompt = (
                task_prompt
                + "\nReturn every ID exactly once. Allowed IDs: "
                + json.dumps(ids)
            )
            raw = ask_llm(system_prompt, retry_prompt, schema)

            try:
                ordered_ids = parse_ranking(raw, incomplete)
                detail = "The retry passed ID validation."
            except (ValueError, TypeError):
                ordered_ids = fallback_ranking(incomplete)
                used_fallback = True
                detail = (
                    "The retry failed ID validation. Used the explicit "
                    "date-and-weighting fallback."
                )

            agent_steps.append({"stage": "ADAPT", "detail": detail})

        return jsonify({
            "recommendation": render_recommendation(
                ordered_ids,
                incomplete,
                used_fallback,
            ),
            "agent_steps": agent_steps,
            "ranking_method": "fallback" if used_fallback else "ai",
        }), 200

    except Exception:
        return jsonify({
            "error": "AI prioritisation request failed",
            "agent_steps": agent_steps,
        }), 502