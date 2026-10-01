import asyncio
import os

from mcp import Client


MCP_SERVER_URL = os.getenv(
    "MCP_SERVER_URL",
    "http://127.0.0.1:8011/mcp",
)


async def _search_notes(student_id: int, keyword: str, limit: int) -> dict:
    async with Client(MCP_SERVER_URL) as client:
        result = await client.call_tool(
            "notebooks_search_notes",
            {
                "student_id": student_id,
                "keyword": keyword,
                "limit": limit,
            },
        )

        if result.is_error:
            raise RuntimeError("The notebook MCP tool returned an error")

        data = result.structured_content
        if not isinstance(data, dict):
            raise RuntimeError("The MCP tool returned no structured result")

        if data.get("status") != "success":
            raise RuntimeError("The notebook MCP request was unsuccessful")

        if not isinstance(data.get("notes"), list):
            raise RuntimeError("The MCP result is missing its notes list")

        return data


def search_notes_via_mcp(
    student_id: int,
    keyword: str,
    limit: int = 10,
) -> dict:
    async def run():
        return await asyncio.wait_for(
            _search_notes(student_id, keyword, limit),
            timeout=15,
        )

    return asyncio.run(run())
