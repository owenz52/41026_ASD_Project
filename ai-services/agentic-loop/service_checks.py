import asyncio

import requests
from mcp import Client


MCP_URL = "http://127.0.0.1:8011/mcp"
RAG_URL = "http://127.0.0.1:5200"


async def check_mcp() -> dict:
    async with Client(MCP_URL) as client:
        tools = await client.list_tools()
        names = sorted(tool.name for tool in tools.tools)

    return {
        "status": "pass" if "assessments_get_upcoming" in names else "fail",
        "tools": names,
    }



def check_rag() -> dict:
    health = requests.get(f"{RAG_URL}/health", timeout=10)
    health.raise_for_status()

    payload = {
        "question": "When is the Architecture Report due?",
        "top_k": 4,
        "feature": "assessments",
    }

    response = requests.post(
        f"{RAG_URL}/query",
        json=payload,
        timeout=60,
    )
    response.raise_for_status()

    result = response.json()
    citations = result.get("citations", [])

    passed = (
        health.json().get("status") == "ok"
        and result.get("grounded") is True
        and bool(citations)
        and bool(result.get("answer"))
        and result.get("insufficient_context") is not True
    )

    return {
        "status": "pass" if passed else "fail",
        "grounded": result.get("grounded"),
        "confidence": result.get("confidence"),
        "generated": result.get("generated"),
        "citation_count": len(citations),
        "cited_sources": [
            citation.get("source") for citation in citations
        ],
        "answer": result.get("answer"),
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