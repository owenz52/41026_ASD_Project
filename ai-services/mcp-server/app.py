"""Shared MCP server.

Exposes the project's data to every feature as a small set of named tools, so
a feature can reach another feature's information through one interface rather
than each team hard-coding calls to each other's services.

Release 1 requires this server to run locally and NOT be containerised, so it
is started directly with Python and is deliberately absent from
docker-compose.yml. It talks to the feature database services on their
published host ports.

Contract
--------
    GET  /health   -> {"status": "ok", "tools": n}
    GET  /tools    -> {"tools": [{name, description, input_schema}, ...]}
    POST /invoke   -> {"tool": name, "arguments": {...}}
                      {"result": ..., "tool": name} on success
                      {"error": "..."} with a 4xx on failure

The server never raises out of a tool. A feature service being unavailable is
reported as a tool error, so one stopped container does not take the MCP
server down for everybody.
"""
import os

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

PORT = int(os.getenv("MCP_PORT", 5100))
TIMEOUT = int(os.getenv("MCP_UPSTREAM_TIMEOUT", 10))


def _url(name, default):
    return os.getenv(name, default).rstrip("/")


# The feature database services, on the ports docker-compose publishes to the
# host. Overridable so the server can be pointed at stubs during testing.
ENROLMENT = _url("ENROLMENT_DB_URL", "http://localhost:5002")
NOTEBOOK = _url("NOTEBOOK_DB_URL", "http://localhost:5004")
CALENDAR = _url("CALENDAR_DB_URL", "http://localhost:5006")
ASSESSMENT = _url("ASSESSMENT_DB_URL", "http://localhost:5008")
EXAM = _url("EXAM_DB_URL", "http://localhost:5010")


class ToolError(Exception):
    """A tool could not complete. Reported to the caller, never raised out."""


def _get(base, path, params=None):
    try:
        response = requests.get(f"{base}{path}", params=params, timeout=TIMEOUT)
    except requests.RequestException as error:
        raise ToolError(f"{base} is unavailable: {type(error).__name__}") from error

    if response.status_code >= 400:
        raise ToolError(f"{base}{path} returned {response.status_code}")

    try:
        return response.json()
    except ValueError as error:
        raise ToolError(f"{base}{path} did not return JSON") from error


def _as_list(body, *keys):
    """Feature services return either a bare list or a wrapped object."""
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for key in keys:
            if isinstance(body.get(key), list):
                return body[key]
    return []


def _require(arguments, name):
    value = arguments.get(name)
    if value in (None, ""):
        raise ToolError(f"'{name}' is required")
    return value


# ------------------------------------------------------------------- tools

def list_calendar_events(arguments):
    """Calendar events for one student, optionally within a date range."""
    params = {"student_id": _require(arguments, "student_id")}
    for optional in ("start_date", "end_date", "subject"):
        if arguments.get(optional):
            params[optional] = arguments[optional]

    events = _as_list(_get(CALENDAR, "/events", params), "events")
    return {"count": len(events), "events": events}


def list_assignments(arguments):
    """Assignments for one student, optionally filtered by status."""
    params = {"student_id": _require(arguments, "student_id")}
    if arguments.get("status"):
        params["status"] = arguments["status"]

    items = _as_list(_get(ASSESSMENT, "/assignments", params), "assignments")
    return {"count": len(items), "assignments": items}


def list_exams(arguments):
    """Exams, optionally narrowed to one student."""
    exams = _as_list(_get(EXAM, "/exams"), "exams")

    student_id = arguments.get("student_id")
    if student_id not in (None, ""):
        exams = [e for e in exams
                 if str(e.get("student_id")) == str(student_id)]

    return {"count": len(exams), "exams": exams}


def list_courses(arguments):
    """The course catalogue."""
    courses = _as_list(_get(ENROLMENT, "/courses"), "courses")
    return {"count": len(courses), "courses": courses}


def list_enrolments(arguments):
    """Enrolments, optionally narrowed to one student."""
    student_id = arguments.get("student_id")

    if student_id not in (None, ""):
        try:
            body = _get(ENROLMENT, f"/enrolments/by-student/{student_id}")
            return {"count": len(_as_list(body, "enrolments")),
                    "enrolments": _as_list(body, "enrolments")}
        except ToolError:
            # Fall back to filtering the full list if that route is absent.
            pass

    enrolments = _as_list(_get(ENROLMENT, "/enrolments"), "enrolments")
    if student_id not in (None, ""):
        enrolments = [e for e in enrolments
                      if str(e.get("student_id")) == str(student_id)]

    return {"count": len(enrolments), "enrolments": enrolments}


def search_notes(arguments):
    """Search the notebook service for notes matching a query."""
    query = _require(arguments, "query")
    notes = _as_list(_get(NOTEBOOK, "/notes/search", {"q": query}), "notes")
    return {"count": len(notes), "query": query, "notes": notes}


def student_overview(arguments):
    """One student's commitments across every feature.

    Reads each service independently so that an unavailable service reduces
    the overview rather than failing it.
    """
    student_id = _require(arguments, "student_id")
    overview = {"student_id": student_id, "unavailable": []}

    for key, fn, args in [
        ("events", list_calendar_events, {"student_id": student_id}),
        ("assignments", list_assignments, {"student_id": student_id}),
        ("exams", list_exams, {"student_id": student_id}),
        ("enrolments", list_enrolments, {"student_id": student_id}),
    ]:
        try:
            overview[key] = fn(args)
        except ToolError as error:
            overview[key] = {"count": 0}
            overview["unavailable"].append({"source": key, "reason": str(error)})

    return overview


TOOLS = [
    {
        "name": "list_calendar_events",
        "description": "List a student's calendar events, optionally within a date range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_id": {"type": "integer", "description": "The student's id"},
                "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                "subject": {"type": "string", "description": "Subject label"},
            },
            "required": ["student_id"],
        },
        "handler": list_calendar_events,
    },
    {
        "name": "list_assignments",
        "description": "List a student's assignments with due dates and weightings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_id": {"type": "integer"},
                "status": {"type": "string",
                           "description": "not_started, in_progress or completed"},
            },
            "required": ["student_id"],
        },
        "handler": list_assignments,
    },
    {
        "name": "list_exams",
        "description": "List exams, optionally for one student.",
        "input_schema": {
            "type": "object",
            "properties": {"student_id": {"type": "integer"}},
        },
        "handler": list_exams,
    },
    {
        "name": "list_courses",
        "description": "List the course catalogue.",
        "input_schema": {"type": "object", "properties": {}},
        "handler": list_courses,
    },
    {
        "name": "list_enrolments",
        "description": "List enrolments, optionally for one student.",
        "input_schema": {
            "type": "object",
            "properties": {"student_id": {"type": "integer"}},
        },
        "handler": list_enrolments,
    },
    {
        "name": "search_notes",
        "description": "Search a student's notes for a phrase.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        "handler": search_notes,
    },
    {
        "name": "student_overview",
        "description": "A student's events, assignments, exams and enrolments together.",
        "input_schema": {
            "type": "object",
            "properties": {"student_id": {"type": "integer"}},
            "required": ["student_id"],
        },
        "handler": student_overview,
    },
]

BY_NAME = {t["name"]: t for t in TOOLS}


def _public(tool):
    return {k: tool[k] for k in ("name", "description", "input_schema")}


# ------------------------------------------------------------------ routes

@app.get("/health")
def health():
    return jsonify({"status": "ok", "tools": len(TOOLS)})


@app.get("/tools")
def tools():
    return jsonify({"tools": [_public(t) for t in TOOLS], "count": len(TOOLS)})


@app.post("/invoke")
def invoke():
    data = request.get_json(silent=True) or {}
    name = data.get("tool")
    arguments = data.get("arguments") or {}

    if not name:
        return jsonify({"error": "'tool' is required"}), 400

    tool = BY_NAME.get(name)
    if tool is None:
        return jsonify({
            "error": f"unknown tool '{name}'",
            "available": sorted(BY_NAME),
        }), 400

    if not isinstance(arguments, dict):
        return jsonify({"error": "'arguments' must be an object"}), 400

    try:
        result = tool["handler"](arguments)
    except ToolError as error:
        return jsonify({"tool": name, "error": str(error)}), 502
    except Exception as error:                      # noqa: BLE001
        return jsonify({"tool": name,
                        "error": f"tool failed: {type(error).__name__}"}), 500

    return jsonify({"tool": name, "arguments": arguments, "result": result})


if __name__ == "__main__":
    print(f"Shared MCP server on http://localhost:{PORT}  ({len(TOOLS)} tools)")
    for tool in TOOLS:
        print(f"  - {tool['name']}")
    app.run(host="0.0.0.0", port=PORT)
