from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings


from mcp_service.tools import (

    get_student_exam_status,
    get_student_exams,
    get_student_exam_summary,
)

mcp = FastMCP(
    "Student Exams MCP",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            "localhost:*",
            "127.0.0.1:*",
            "host.docker.internal:*",
        ],
    ),
)


# Set the HTTP server port
mcp.settings.host = "0.0.0.0"
mcp.settings.port = 8050




@mcp.tool()
def student_exam_status(student_id: int):
    """Get the number of completed and non-completed exams."""
    return get_student_exam_status(student_id)


@mcp.tool()
def student_exams(student_id: int):
    """Get all active exams belonging to a student."""
    return get_student_exams(student_id)


@mcp.tool()
def student_exam_summary(student_id: int):
    """
    Get a complete student exam summary including
    student information, subjects, exam counts and exams.
    """
    return get_student_exam_summary(student_id)


if __name__ == "__main__":
    print("Starting Student Exams MCP Server...")
    print("Server status: RUNNING")

    mcp.run(transport="sse")

