import asyncio
import os

from mcp import Client

MCP_SERVER_URL = os.getenv(
    "MCP_SERVER_URL",
    "http://127.0.0.1:8011/mcp",
)

async def _get_courses(available_only: bool) -> dict:
    async with Client(MCP_SERVER_URL) as client:
        result = await client.call_tool(
            "enrolment_get_courses",
            {"available_only": available_only},
        )

        if result.is_error:
            raise RuntimeError("The enrolment MCP tool returned an error")
        data = result.structured_content
        if not isinstance(data, dict):
            raise RuntimeError("MCP returned no structured result")
        if data.get("status") != "success":
            raise RuntimeError("MCP returned an unsuccessful status")
        if not isinstance(data.get("courses"), list):
            raise RuntimeError("MCP returned no courses list")
        return data

def get_courses_via_mcp(available_only: bool = True) -> dict:
    async def run():
        return await asyncio.wait_for(
            _get_courses(available_only),
            timeout=10,
        )
    return asyncio.run(run())