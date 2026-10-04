"""Client for the shared MCP server.

The shared server (ai-services/mcp-server) runs the MCP SDK over streamable
HTTP with a JSON-RPC endpoint at /mcp. It is stateless, so tools/list and
tools/call can be issued directly without an initialize handshake.

Wire format
-----------
    POST /mcp
    Content-Type: application/json
    Accept: application/json, text/event-stream

    {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
     "params": {"name": tool, "arguments": {...}}}

A tool result arrives as result.structuredContent when the tool declares a
return type, and always as JSON text in result.content[0].text. A tool that
ran but failed is reported with result.isError set, still over HTTP 200, so
the status code alone is not enough to decide success.

Every function returns a structured result rather than raising, so an
unavailable MCP server degrades the calendar rather than breaking the page.
"""
import itertools
import json

import requests

from config import MCP_ENABLED, MCP_PATH, MCP_SERVER_URL, MCP_TIMEOUT_SECONDS

HEADERS = {
    "Content-Type": "application/json",
    # The server negotiates between a JSON body and an SSE stream; it replies
    # with JSON when this is offered, but the header must list both.
    "Accept": "application/json, text/event-stream",
}

_ids = itertools.count(1)


def _endpoint():
    """The JSON-RPC endpoint.

    The project's compose files set MCP_SERVER_URL with the path already
    included (http://host:8011/mcp), so appending MCP_PATH again would produce
    /mcp/mcp. The path is only added when it is not there already.
    """
    base = MCP_SERVER_URL.rstrip("/")
    path = MCP_PATH if MCP_PATH.startswith("/") else f"/{MCP_PATH}"

    if base.endswith(path):
        return base
    return f"{base}{path}"


def _disabled():
    return {"ok": False, "available": False,
            "error": "MCP is disabled in this environment"}


def _unreachable(error):
    return {"ok": False, "available": False,
            "error": f"MCP server unreachable at {_endpoint()}: {error}"}


def _rpc(method, params=None):
    """One JSON-RPC call. Returns (result, error_message)."""
    payload = {"jsonrpc": "2.0", "id": next(_ids), "method": method}
    if params is not None:
        payload["params"] = params

    try:
        response = requests.post(_endpoint(), json=payload, headers=HEADERS,
                                 timeout=MCP_TIMEOUT_SECONDS)
    except requests.RequestException as error:
        return None, f"unreachable: {type(error).__name__}"

    if response.status_code >= 400:
        return None, f"server returned {response.status_code}"

    try:
        body = response.json()
    except ValueError:
        # An SSE stream rather than a JSON body: pull the data lines out.
        text = response.text
        for line in text.splitlines():
            if line.startswith("data:"):
                try:
                    body = json.loads(line[5:].strip())
                    break
                except ValueError:
                    continue
        else:
            return None, "response was not JSON"

    if isinstance(body, dict) and body.get("error"):
        message = body["error"]
        if isinstance(message, dict):
            message = message.get("message", str(message))
        return None, str(message)

    return (body or {}).get("result"), None


def _normalise_tool(raw):
    """MCP uses inputSchema; the frontend and routes use input_schema."""
    return {
        "name": raw.get("name", ""),
        "description": raw.get("description", ""),
        "input_schema": raw.get("inputSchema") or raw.get("input_schema") or {},
    }


def list_tools():
    """The tools the shared MCP server has registered."""
    if not MCP_ENABLED:
        return _disabled()

    result, error = _rpc("tools/list")
    if error:
        return _unreachable(error)

    tools = [_normalise_tool(t) for t in (result or {}).get("tools", [])]
    tools = [t for t in tools if t["name"]]

    return {"ok": True, "available": True, "tools": tools, "count": len(tools)}


def _extract(result):
    """Pull the tool's return value out of an MCP tool result.

    structuredContent is preferred because it is already typed; the text block
    is the fallback and carries the same value as a JSON string.
    """
    if not isinstance(result, dict):
        return result

    if "structuredContent" in result:
        return result["structuredContent"]

    for block in result.get("content") or []:
        if block.get("type") == "text" and block.get("text"):
            try:
                return json.loads(block["text"])
            except ValueError:
                return block["text"]

    return result


def _error_text(result):
    for block in (result or {}).get("content") or []:
        if block.get("text"):
            return block["text"]
    return "the tool reported an error"


def invoke(tool, arguments=None):
    """Call one registered tool and return its structured result."""
    if not MCP_ENABLED:
        return _disabled()

    if not tool:
        return {"ok": False, "available": True, "error": "tool name is required"}

    result, error = _rpc("tools/call",
                         {"name": tool, "arguments": arguments or {}})
    if error:
        return _unreachable(error)

    # A tool can fail while the transport succeeds.
    if isinstance(result, dict) and result.get("isError"):
        return {"ok": False, "available": True, "tool": tool,
                "error": _error_text(result)}

    return {"ok": True, "available": True, "tool": tool,
            "arguments": arguments or {}, "result": _extract(result)}


def health():
    """Whether the shared MCP server is reachable, for the diagnostics view."""
    if not MCP_ENABLED:
        return {"enabled": False, "reachable": False, "url": _endpoint(),
                "reason": "disabled by configuration"}

    result, error = _rpc("tools/list")
    if error:
        return {"enabled": True, "reachable": False, "url": _endpoint(),
                "error": error}

    return {"enabled": True, "reachable": True, "url": _endpoint(),
            "tools": len((result or {}).get("tools", []))}
