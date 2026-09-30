import asyncio
import os

from mcp import Client


MCP_SERVER_URL = os.getenv(
    "MCP_SERVER_URL",
    "http://127.0.0.1:8011/mcp",
)


async def _get_upcoming(student_id: int, days_ahead: int) -> dict:
    async with Client(MCP_SERVER_URL) as client:
        result = await client.call_tool(
            "assessments_get_upcoming",
            {
                "student_id": student_id,
                "days_ahead": days_ahead,
            },
        )

        if result.is_error:
            raise RuntimeError("The assessment MCP tool returned an error")

        data = result.structured_content
        if not isinstance(data, dict):
            raise RuntimeError("The MCP tool returned no structured result")

        if data.get("status") != "success":
            raise RuntimeError("The assessment MCP request was unsuccessful")

        if not isinstance(data.get("assignments"), list):
            raise RuntimeError("The MCP result is missing its assignments list")

        return data


def get_upcoming_assessments(
    student_id: int,
    days_ahead: int = 14,
) -> dict:
    async def run():
        return await asyncio.wait_for(
            _get_upcoming(student_id, days_ahead),
            timeout=20,
        )

    return asyncio.run(run())