"""Tool boundaries for the calendar's access to the shared MCP server.

The shared server registers tools for every feature. The calendar may only use
its own, and only with arguments it has declared. This is enforced here, in the
backend, because the browser is not trusted: it could otherwise name any tool
(another feature's, or a future write tool) or pass another student's id.

    ALLOWED_TOOLS   which tools the calendar may call, and their argument rules
    filter_tools    hides every other tool from /ai/mcp/tools
    validate        checks one call; returns (arguments, None) or (None, error)

student_id is never taken from the arguments. The route supplies it and
validate() writes it over anything the client sent.
"""
import re
from datetime import date

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

ALLOWED_TOOLS = {
    "calendar_get_upcoming_events": {
        "days_ahead": {"type": "int", "min": 1, "max": 60, "default": 7},
    },
    "calendar_find_conflicts": {
        "day": {"type": "date", "default": ""},
    },
}


def is_allowed(tool):
    return tool in ALLOWED_TOOLS


def _limits(tool):
    """Human-readable argument limits, shown next to the inputs."""
    limits = {}
    for name, rule in ALLOWED_TOOLS[tool].items():
        if rule["type"] == "int":
            limits[name] = f"{rule['min']} to {rule['max']}"
        elif rule["type"] == "date":
            limits[name] = "YYYY-MM-DD, blank for today"
    return limits


def filter_tools(listing):
    """Keep only the calendar's tools in a list_tools() result."""
    if not isinstance(listing, dict) or not listing.get("ok"):
        return listing

    tools = []
    for tool in listing.get("tools", []):
        if is_allowed(tool["name"]):
            tools.append({**tool, "limits": _limits(tool["name"])})

    return {**listing, "tools": tools, "count": len(tools)}


def validate(tool, arguments, student_id):
    """Check a call against the policy."""
    if not is_allowed(tool):
        return None, f"tool '{tool}' is not available to the calendar"

    arguments = arguments if isinstance(arguments, dict) else {}
    rules = ALLOWED_TOOLS[tool]

    unknown = set(arguments) - set(rules) - {"student_id"}
    if unknown:
        return None, f"unexpected argument(s): {', '.join(sorted(unknown))}"

    clean = {"student_id": int(student_id)}

    for name, rule in rules.items():
        value = arguments.get(name, rule["default"])

        if rule["type"] == "int":
            if isinstance(value, bool) or not isinstance(value, (int, float)) \
                    or int(value) != value:
                return None, f"{name} must be a whole number"
            value = int(value)
            if not rule["min"] <= value <= rule["max"]:
                return None, f"{name} must be between {rule['min']} and {rule['max']}"

        elif rule["type"] == "date" and value != "":
            if not isinstance(value, str) or not DATE_PATTERN.match(value):
                return None, f"{name} must be a date in YYYY-MM-DD format"
            try:
                date.fromisoformat(value)
            except ValueError:
                return None, f"{name} is not a real calendar date"

        clean[name] = value

    return clean, None
