import asyncio

import requests
from mcp import Client


MCP_URL = "http://127.0.0.1:8011/mcp"
RAG_URL = "http://127.0.0.1:8012"


async def check_mcp() -> dict:
    async with Client(MCP_URL) as client:
        tools = await client.list_tools()
        names = sorted(tool.name for tool in tools.tools)

    return {
        "status": "pass" if "assessments_get_upcoming" in names else "fail",
        "tools": names,
    }


def check_rag() -> dict:
    health = requests.get(f"{RAG_URL}/health", timeout=5)
    health.raise_for_status()

    payload = {
        "query": "When is the Architecture Report due?",
        "feature": "assessments",
        "student_id": 1,
        "documents": [{
            "feature": "assessments",
            "student_id": 1,
            "chunk_id": "validation:assessment",
            "source_id": "validation:assessment",
            "authority_tier": "tier_1",
            "text": "The Architecture Report is due on 2026-10-05.",
        }],
    }

    response = requests.post(f"{RAG_URL}/retrieve", json=payload, timeout=15)
    response.raise_for_status()
    result = response.json()
    matches = result.get("results", [])

    passed = (
        health.json().get("status") == "ok"
        and result.get("status") == "success"
        and len(matches) > 0
        and matches[0].get("source_id") == "validation:assessment"
    )

    return {
        "status": "pass" if passed else "fail",
        "retrieved_sources": [item["source_id"] for item in matches],
    }


def check_shared_services() -> dict:
    checks = {}

    try:
        checks["mcp"] = asyncio.run(check_mcp())
    except Exception as exc:
        checks["mcp"] = {"status": "fail", "error": str(exc)}

    try:
        checks["rag"] = check_rag()
    except Exception as exc:
        checks["rag"] = {"status": "fail", "error": str(exc)}

    return {
        "status": (
            "pass"
            if all(item["status"] == "pass" for item in checks.values())
            else "fail"
        ),
        "checks": checks,
    }