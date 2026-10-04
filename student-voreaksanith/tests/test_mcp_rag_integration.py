"""Release 1 tests: calendar access to the shared MCP and RAG servers.

Stub MCP and RAG servers stand in for the shared ones, so every path can be
exercised — including the cases that matter most for marking: a grounded
answer with citations and a confidence category, and an insufficient-context
response when nothing relevant was retrieved.
"""
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

CAL = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PORT, MCP_PORT, RAG_PORT = 8000, 15100, 15200
BASE = f"http://localhost:{PORT}/calendar-api"

IS_WINDOWS = os.name == "nt"
SPAWN = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if IS_WINDOWS
         else {"start_new_session": True})
LOG = os.path.join(tempfile.gettempdir(), "calendar_r1_server.log")

results = []


def check(label, ok, detail=""):
    results.append(ok)
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  -- {detail}" if detail else ""))


# What the stub servers should return next.
MODE = {"mcp": "ok", "rag": "grounded"}

TOOLS = [
    {"name": "list_calendar_events",
     "description": "List a student's calendar events in a date range",
     "input_schema": {"type": "object",
                      "properties": {"student_id": {"type": "integer"}}}},
    {"name": "get_assessment_summary",
     "description": "Summarise outstanding assessments for a student",
     "input_schema": {"type": "object",
                      "properties": {"student_id": {"type": "integer"}}}},
]


class MCPStub(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        if MODE["mcp"] == "down":
            self.send_response(503); self.end_headers(); return
        if self.path.startswith("/health"):
            return self._send(200, {"status": "ok"})
        self._send(200, {"tools": TOOLS})

    def do_POST(self):
        if MODE["mcp"] == "down":
            self.send_response(503); self.end_headers(); return
        n = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(n) or "{}")
        tool = payload.get("tool")

        if tool not in [t["name"] for t in TOOLS]:
            return self._send(400, {"error": f"unknown tool '{tool}'"})

        self._send(200, {"result": {
            "tool": tool,
            "events": [{"event_id": 1, "title": "ASD Lecture",
                        "start_time": "2026-09-02 10:00"}],
            "count": 1,
        }})


class RAGStub(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        if MODE["rag"] == "down":
            self.send_response(503); self.end_headers(); return
        self._send(200, {"status": "ok"})

    def do_POST(self):
        mode = MODE["rag"]
        if mode == "down":
            self.send_response(503); self.end_headers(); return

        if mode == "insufficient":
            return self._send(200, {"grounded": False, "answer": "",
                                    "citations": [], "confidence": "none"})

        if mode == "ungrounded":
            # An answer with no citations: must be rejected by the client.
            return self._send(200, {"answer": "The exam is definitely on Monday.",
                                    "citations": [], "confidence": "high"})

        if mode == "numeric_confidence":
            return self._send(200, {
                "answer": "Assignment 2 is due on 25 September 2026.",
                "sources": [{"document": "assessment_tracker.md",
                             "text": "Assignment 2 due 2026-09-25", "score": 0.91}],
                "confidence": 0.91})

        self._send(200, {
            "answer": "Your next exam is ASD101 Final Exam on 10 October 2026 "
                      "at 09:00.",
            "citations": [
                {"source": "exam_timetable.md",
                 "snippet": "ASD101 Final Exam, 2026-10-10, 09:00", "score": 0.93},
                {"source": "calendar_events.md",
                 "snippet": "Revision block before ASD101", "score": 0.71},
                {"source": "unit_outline.md",
                 "snippet": "Final examinations are held in week 13", "score": 0.66},
            ],
            "confidence": "high"})


for port, handler in [(MCP_PORT, MCPStub), (RAG_PORT, RAGStub)]:
    server = HTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

db = os.path.join(CAL, "database", "data", "calendar.db")
if os.path.exists(db):
    os.remove(db)

proc = subprocess.Popen(
    [sys.executable, "run_local.py", str(PORT),
     "--mcp-url", f"http://127.0.0.1:{MCP_PORT}",
     "--rag-url", f"http://127.0.0.1:{RAG_PORT}"], cwd=CAL,
    stdout=open(LOG, "w"), stderr=subprocess.STDOUT, **SPAWN,
    env={**os.environ, "PYTHONUNBUFFERED": "1",
         "MCP_SERVER_URL": f"http://127.0.0.1:{MCP_PORT}",
         "RAG_SERVER_URL": f"http://127.0.0.1:{RAG_PORT}"})


def stop(p):
    try:
        if IS_WINDOWS:
            p.terminate()
        else:
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        p.wait(timeout=10)
    except Exception:
        try:
            p.kill()
        except Exception:
            pass


up = False
for _ in range(50):
    try:
        requests.get(f"http://localhost:{PORT}/", timeout=1); up = True; break
    except requests.RequestException:
        time.sleep(0.4)

try:
    if not up:
        print(open(LOG).read()[-2000:]); raise SystemExit("server did not start")

    # Pre-flight. If the stubs are not reachable, or the backend resolved a
    # different URL than the one passed in, every check below fails for the
    # same reason and the output is easier to read if that is said once.
    print("\n--- Pre-flight ---")
    for name, port in [("MCP stub", MCP_PORT), ("RAG stub", RAG_PORT)]:
        try:
            requests.get(f"http://127.0.0.1:{port}/health", timeout=5)
            reachable = True
        except requests.RequestException as error:
            reachable = False
            detail = type(error).__name__
        check(f"{name} reachable from the test process", reachable,
              "" if reachable else detail)

    diag = requests.get(f"{BASE}/ai/diagnostics", timeout=30).json()
    mcp_url = diag.get("mcp", {}).get("url", "?")
    rag_url = diag.get("rag", {}).get("url", "?")
    check("backend picked up MCP_SERVER_URL",
          str(MCP_PORT) in mcp_url, f"backend is using {mcp_url}")
    check("backend picked up RAG_SERVER_URL",
          str(RAG_PORT) in rag_url, f"backend is using {rag_url}")
    check("MCP enabled in the backend",
          diag.get("mcp", {}).get("enabled") is True,
          f"enabled={diag.get('mcp', {}).get('enabled')}")
    check("RAG enabled in the backend",
          diag.get("rag", {}).get("enabled") is True,
          f"enabled={diag.get('rag', {}).get('enabled')}")

    print("\n--- MCP: tools are registered and reachable through the backend ---")
    r = requests.get(f"{BASE}/ai/mcp/tools", timeout=20)
    body = r.json()
    check("tools endpoint returns 200", r.status_code == 200)
    check("tools listed", body.get("count") == 2, str(body.get("count")))
    names = [t["name"] for t in body.get("tools", [])]
    check("tool names normalised", "list_calendar_events" in names, str(names))
    tools = body.get("tools") or []
    check("input schema carried through",
          bool(tools and tools[0].get("input_schema")),
          "no tools returned" if not tools else "")

    print("\n--- MCP: invoking a tool returns a structured result ---")
    r = requests.post(f"{BASE}/ai/mcp/invoke",
                      json={"tool": "list_calendar_events",
                            "arguments": {"student_id": 1}}, timeout=20)
    body = r.json()
    check("invoke returns 200", r.status_code == 200)
    check("result is structured", isinstance(body.get("result"), dict),
          str(type(body.get("result"))))
    check("tool echoed back", body.get("tool") == "list_calendar_events")
    check("arguments echoed back", body.get("arguments") == {"student_id": 1})

    print("\n--- MCP: boundaries and validation ---")
    r = requests.post(f"{BASE}/ai/mcp/invoke", json={"tool": "delete_everything"},
                      timeout=20)
    check("unknown tool rejected", r.json().get("ok") is False, str(r.json())[:70])
    r = requests.post(f"{BASE}/ai/mcp/invoke", json={}, timeout=20)
    check("missing tool name rejected", r.status_code == 400)

    print("\n--- RAG: grounded answer with citations and confidence ---")
    r = requests.post(f"{BASE}/ai/rag/ask",
                      json={"question": "When is my next exam?"}, timeout=60)
    body = r.json()
    check("ask returns 200", r.status_code == 200)
    check("answer is grounded", body.get("grounded") is True)
    check("answer returned", len(body.get("answer") or "") > 20,
          (body.get("answer") or "")[:50])
    check("citations returned", len(body.get("citations", [])) == 3,
          str(len(body.get("citations", []))))
    cites = body.get("citations") or []
    check("citation has source and snippet",
          bool(cites and cites[0].get("source") and cites[0].get("snippet")),
          "no citations returned" if not cites else "")
    check("confidence category present",
          body.get("confidence") in ("high", "medium", "low"),
          str(body.get("confidence")))

    print("\n--- RAG: numeric confidence is mapped to a category ---")
    MODE["rag"] = "numeric_confidence"
    body = requests.post(f"{BASE}/ai/rag/ask",
                         json={"question": "When is assignment 2 due?"},
                         timeout=60).json()
    check("numeric score mapped to a category", body.get("confidence") == "high",
          str(body.get("confidence")))
    cites = body.get("citations") or []
    check("alternative citation shape normalised",
          bool(cites) and cites[0].get("source") == "assessment_tracker.md",
          str(cites[:1]))

    print("\n--- RAG: insufficient context is reported, not invented ---")
    MODE["rag"] = "insufficient"
    body = requests.post(f"{BASE}/ai/rag/ask",
                         json={"question": "What is the capital of France?"},
                         timeout=60).json()
    check("not grounded", body.get("grounded") is False)
    check("confidence is insufficient", body.get("confidence") == "insufficient")
    check("insufficient-context message returned",
          "not enough relevant material" in (body.get("answer") or ""),
          (body.get("answer") or "")[:60])

    print("\n--- RAG: an answer with no citations is refused ---")
    MODE["rag"] = "ungrounded"
    body = requests.post(f"{BASE}/ai/rag/ask",
                         json={"question": "When is the exam?"}, timeout=60).json()
    check("ungrounded answer downgraded", body.get("grounded") is False,
          str(body.get("grounded")))
    check("unsupported answer not shown to the student",
          "definitely on Monday" not in (body.get("answer") or ""))

    print("\n--- RAG: validation ---")
    r = requests.post(f"{BASE}/ai/rag/ask", json={}, timeout=20)
    check("missing question rejected", r.status_code == 400)

    print("\n--- Degradation: both shared servers down ---")
    MODE["mcp"], MODE["rag"] = "down", "down"
    r = requests.get(f"{BASE}/ai/mcp/tools", timeout=20)
    check("MCP reports unavailable", r.json().get("available") is False)
    r = requests.post(f"{BASE}/ai/rag/ask",
                      json={"question": "When is my exam?"}, timeout=60)
    check("RAG reports unavailable", r.json().get("available") is False)
    check("RAG still returns a confidence field",
          r.json().get("confidence") == "insufficient")

    print("\n--- Release 0 functionality still works ---")
    events = requests.get(f"{BASE}/events", params={"student_id": 1},
                          timeout=20).json()
    check("calendar events still served", events.get("count", 0) > 0,
          str(events.get("count")))
    r = requests.post(f"{BASE}/ai/briefing", json={"student_id": 1}, timeout=60)
    check("briefing still works", r.status_code == 200)

    print("\n--- Diagnostics reports both shared servers ---")
    d = requests.get(f"{BASE}/ai/diagnostics", timeout=30).json()
    check("diagnostics includes mcp", "mcp" in d and "url" in d["mcp"])
    check("diagnostics includes rag", "rag" in d and "url" in d["rag"])

finally:
    stop(proc)

print(f"\n{'=' * 58}\n  {sum(results)}/{len(results)} checks passed\n{'=' * 58}")
sys.exit(0 if all(results) else 1)
