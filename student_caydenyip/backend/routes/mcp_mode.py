import asyncio
import os
import json

from flask import Blueprint, jsonify, request

from mcp import ClientSession
from mcp.client.sse import sse_client


mcp_bp = Blueprint(
    "mcp_mode",
    __name__,
)


# ==================================================
# MCP CONFIGURATION
# ==================================================

MCP_SERVER_URL = os.getenv(
    "MCP_SERVER_URL",
    "http://host.docker.internal:8050/sse",
)


AVAILABLE_TOOLS = {
    "student_exam_status",
    "student_exams",
    "student_exam_summary",
}


# ==================================================
# MCP MODE CONFIGURATION
# ==================================================

def mcp_mode_is_enabled(req) -> bool:

    enabled = os.getenv(
        "MCP_ENABLED",
        "true",
    ).strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

    if not enabled:
        return False

    mode_header = req.headers.get(
        "X-MCP-Mode",
        "on",
    ).strip().lower()

    return mode_header in (
        "1",
        "true",
        "yes",
        "on",
    )


def mcp_disabled_response():

    return jsonify({
        "error": "MCP Mode is disabled.",
    }), 403


# ==================================================
# MCP RESULT SERIALIZATION
# ==================================================



def serialize_mcp_result(result):

    output = []

    for content in result.content:

        if hasattr(content, "text"):

            try:
                output.append(
                    json.loads(content.text)
                )
            except (json.JSONDecodeError, TypeError):
                output.append(content.text)

        elif hasattr(content, "data"):

            output.append(content.data)

        else:

            output.append(str(content))

    return output



# ==================================================
# CALL MCP SERVER
# ==================================================

async def _call_mcp_tool(
    tool_name,
    student_id,
):

    async with sse_client(
        MCP_SERVER_URL
    ) as streams:

        read_stream = streams[0]
        write_stream = streams[1]

        async with ClientSession(
            read_stream,
            write_stream,
        ) as session:

            # --------------------------------------
            # Initialize MCP session
            # --------------------------------------

            await session.initialize()

            # --------------------------------------
            # Call MCP tool
            # --------------------------------------

            result = await session.call_tool(
                tool_name,
                {
                    "student_id": student_id,
                },
            )

            return result


def call_mcp_tool(
    tool_name,
    student_id,
):

    return asyncio.run(
        _call_mcp_tool(
            tool_name,
            student_id,
        )
    )


# ==================================================
# MCP API TEST ENDPOINT
# ==================================================

@mcp_bp.post("/mcp/test")
def mcp_test():

    # ------------------------------------------
    # Check MCP mode
    # ------------------------------------------

    if not mcp_mode_is_enabled(request):
        return mcp_disabled_response()

    # ------------------------------------------
    # Read JSON body
    # ------------------------------------------

    data = request.get_json(
        silent=True
    )

    if not isinstance(data, dict):

        return jsonify({
            "error": "Request body must be valid JSON.",
        }), 400

    # ------------------------------------------
    # Get tool
    # ------------------------------------------

    tool = str(
        data.get(
            "tool",
            "",
        )
    ).strip()

    if not tool:

        return jsonify({
            "error": "tool is required.",
        }), 400

    # ------------------------------------------
    # Validate tool
    # ------------------------------------------

    if tool not in AVAILABLE_TOOLS:

        return jsonify({
            "error": f"Unknown MCP tool: {tool}",
            "available_tools": sorted(
                AVAILABLE_TOOLS
            ),
        }), 400

    # ------------------------------------------
    # Get student ID
    # ------------------------------------------

    student_id = data.get(
        "student_id"
    )

    if student_id is None:

        return jsonify({
            "error": "student_id is required.",
        }), 400

    # ------------------------------------------
    # Validate student ID
    # ------------------------------------------

    try:

        student_id = int(
            student_id
        )

    except (TypeError, ValueError):

        return jsonify({
            "error": "student_id must be an integer.",
        }), 400

    if student_id <= 0:

        return jsonify({
            "error": "student_id must be greater than zero.",
        }), 400

    # ------------------------------------------
    # Call MCP server
    # ------------------------------------------

    try:

        result = call_mcp_tool(
            tool,
            student_id,
        )

        serialized_result = (
            serialize_mcp_result(
                result
            )
        )

        # --------------------------------------
        # Return response
        # --------------------------------------

        return jsonify(serialized_result), 200


    except Exception as exc:

        return jsonify({
            "success": False,
            "error": "MCP tool request failed.",
            "details": str(exc),
        }), 503
