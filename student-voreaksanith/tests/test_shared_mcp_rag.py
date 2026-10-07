"""The calendar against the team's REAL shared MCP and RAG servers.

Nothing in the AI chain is stubbed: ai-services/mcp-server and
ai-services/rag-server are started as they ship, and the calendar's clients
talk to them over their real protocols. Only the other teams' backends and
Ollama are stubbed, because they are not part of this integration.
"""
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAL = os.path.join(REPO, "student-voreaksanith")
MCP_DIR = os.path.join(REPO, "ai-services", "mcp-server")
RAG_DIR = os.path.join(REPO, "ai-services", "rag-server")

APP_PORT = 8000
MCP_PORT, RAG_PORT = 8011, 8012
ASSESS_PORT, OLLAMA_PORT, EXAM_PORT = 15907, 15911, 15910
BASE = f"http://localhost:{APP_PORT}/calendar-api"

LOGS = tempfile.gettempdir()
procs = []
results = []


def check(label, ok, detail=""):
    results.append(ok)
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  -- {detail}" if detail else ""))


def ahead(days):
    """A date this many days from today. Negative is the past."""
    return (date.today() + timedelta(days=days)).isoformat()


EXAMS = [
    {"exam_id": 1, "student_id": 1, "course_id": 101,
     "exam_name": "ASD101 Final Examination", "exam_date": ahead(21),
     "exam_time": "09:00", "status": "Uncompleted"},
]

ASSIGNMENTS = [
    {"assignment_id": 1, "student_id": 1, "course_id": 41026,
     "title": "Software Architecture Report", "due_date": ahead(5),
     "weighting": 35, "status": "in_progress"},
    {"assignment_id": 2, "student_id": 1, "course_id": 31271,
     "title": "Finished Already", "due_date": ahead(-2),
     "weighting": 10, "status": "completed"},
    {"assignment_id": 3, "student_id": 1, "course_id": 48024,
     "title": "Overdue Integration Task", "due_date": ahead(-18),
     "weighting": 20, "status": "not_started"},
    {"assignment_id": 4, "student_id": 1, "course_id": 31271,
     "title": "Peer Review Submission", "due_date": ahead(12),
     "weighting": 10, "status": "not_started"},
    {"assignment_id": 5, "student_id": 1, "course_id": 41026,
     "title": "Quiz Completed Early", "due_date": ahead(8),
     "weighting": 5, "status": "completed"},
]

MODE = {"ollama": "ok"}


class ExamStub(BaseHTTPRequestHandler):
    """Mirrors the exam service, which requires student_id and answers 400
    without it."""

    def log_message(self, *a): pass

    def do_GET(self):
        if "student_id=" not in self.path:
            body = json.dumps({"error": "student_id required"}).encode()
            self.send_response(400)
        else:
            sid = self.path.split("student_id=")[1].split("&")[0]
            body = json.dumps(
                [e for e in EXAMS if str(e["student_id"]) == sid]).encode()
            self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)


class AssessStub(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        body = json.dumps(ASSIGNMENTS).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)


class OllamaStub(BaseHTTPRequestHandler):
    """Stands in for Ollama. The shared RAG server calls /api/generate and
    requires the answer to cite a source id, or it refuses to answer."""

    def log_message(self, *a): pass

    def do_POST(self):
        if MODE["ollama"] == "down":
            self.send_response(503); self.end_headers(); return

        length = int(self.headers.get("Content-Length", 0))
        prompt = json.loads(self.rfile.read(length)).get("prompt", "")

        if MODE["ollama"] == "uncited":
            answer = "Your deadline is definitely next Monday."
        elif MODE["ollama"] == "refuses":
            answer = "I don't have enough relevant context to answer that."
        else:
            # Cite the first source id offered, as the prompt instructs.
            source = "calendar:1"
            if "Source [" in prompt:
                source = prompt.split("Source [")[1].split("]")[0]
            answer = f"Your Assignment 2 is due on 25 September 2026 [{source}]."

        body = json.dumps({"response": answer}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)


for port, handler in [(ASSESS_PORT, AssessStub), (OLLAMA_PORT, OllamaStub),
                     (EXAM_PORT, ExamStub)]:
    srv = HTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()


def start(cmd, cwd, env, name):
    p = subprocess.Popen(cmd, cwd=cwd,
                         stdout=open(os.path.join(LOGS, f"{name}.log"), "w"),
                         stderr=subprocess.STDOUT, start_new_session=True,
                         env={**os.environ, "PYTHONUNBUFFERED": "1", **env})
    procs.append((p, name))
    return p


def wait(url, tries=70):
    for _ in range(tries):
        try:
            requests.get(url, timeout=1); return True
        except requests.RequestException:
            time.sleep(0.5)
    return False


db = os.path.join(CAL, "database", "data", "calendar.db")
if os.path.exists(db):
    os.remove(db)

# The team's real MCP server.
start([sys.executable, "server.py"], MCP_DIR,
      {"ASSESSMENT_BACKEND_URL": f"http://127.0.0.1:{ASSESS_PORT}",
       "CALENDAR_DATABASE_URL": f"http://127.0.0.1:{APP_PORT}/db"}, "mcp")

# The team's real RAG server. Its Ollama URL is hard-coded to 127.0.0.1:11434,
# so the stub is reached by patching that module attribute at startup.
start([sys.executable, "-c",
       "import rag_answer;"
       f"rag_answer.OLLAMA_URL='http://127.0.0.1:{OLLAMA_PORT}/api/generate';"
       "exec(open('server.py').read())"], RAG_DIR, {}, "rag")

# The real calendar, pointed at both real servers.
start([sys.executable, "run_local.py", str(APP_PORT),
       "--mcp-url", f"http://127.0.0.1:{MCP_PORT}",
       "--rag-url", f"http://127.0.0.1:{RAG_PORT}",
       "--assessment-url", f"http://127.0.0.1:{ASSESS_PORT}",
       "--exam-url", f"http://127.0.0.1:{EXAM_PORT}"], CAL, {}, "calendar")

try:
    for url, name in [(f"http://127.0.0.1:{RAG_PORT}/health", "rag"),
                      (f"http://localhost:{APP_PORT}/", "calendar")]:
        if not wait(url):
            print(open(os.path.join(LOGS, f"{name}.log")).read()[-1500:])
            raise SystemExit(f"{name} did not start")

    # The MCP server has no GET endpoint, so readiness is a tools/list call.
    ready = False
    for _ in range(70):
        try:
            r = requests.post(f"http://127.0.0.1:{MCP_PORT}/mcp",
                              headers={"Content-Type": "application/json",
                                       "Accept": "application/json, text/event-stream"},
                              json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                              timeout=2)
            if r.status_code == 200:
                ready = True; break
        except requests.RequestException:
            time.sleep(0.5)
    if not ready:
        print(open(os.path.join(LOGS, "mcp.log")).read()[-1500:])
        raise SystemExit("MCP server did not start")

    print("\n--- The calendar reaches the real MCP server ---")
    d = requests.get(f"{BASE}/ai/diagnostics", timeout=40).json()
    check("diagnostics reports MCP reachable", d["mcp"]["reachable"] is True,
          str(d["mcp"]))
    check("diagnostics reports RAG reachable", d["rag"]["reachable"] is True,
          str(d["rag"]))

    body = requests.get(f"{BASE}/ai/mcp/tools", timeout=40).json()
    names = [t["name"] for t in body.get("tools", [])]
    check("the calendar tool is listed",
          names == ["calendar_get_upcoming_events"], str(names))
    check("other features' tools are hidden from the calendar",
          "assessments_get_upcoming" not in names, str(names))
    tools = body.get("tools") or []
    check("MCP inputSchema mapped to input_schema",
          bool(tools and tools[0].get("input_schema", {}).get("properties")),
          "no tools returned" if not tools
          else str(tools[0].get("input_schema"))[:60])
    check("argument limits sent to the frontend",
          all(t.get("limits") for t in tools), str([t.get("limits") for t in tools]))

    print("\n--- Invoking the calendar tool through the calendar backend ---")
    r = requests.post(f"{BASE}/ai/mcp/invoke",
                      json={"tool": "calendar_get_upcoming_events",
                            "student_id": 1,
                            "arguments": {"days_ahead": 60}}, timeout=40)
    result = r.json().get("result") or {}
    check("tool returned structured content", r.status_code == 200
          and isinstance(result, dict), str(r.status_code))
    check("result has the declared fields",
          {"status", "as_of", "count", "events"} <= set(result), str(list(result)))
    check("count matches the events returned",
          result.get("count") == len(result.get("events", [])))

    print("\n--- Tool boundaries ---")
    r = requests.post(f"{BASE}/ai/mcp/invoke",
                      json={"tool": "assessments_get_upcoming", "student_id": 1,
                            "arguments": {"days_ahead": 7}}, timeout=40)
    check("another feature's tool is refused (403)", r.status_code == 403,
          str(r.status_code))
    r = requests.post(f"{BASE}/ai/mcp/invoke",
                      json={"tool": "no_such_tool", "student_id": 1}, timeout=40)
    check("unknown tool is refused (403)", r.status_code == 403,
          str(r.status_code))
    r = requests.post(f"{BASE}/ai/mcp/invoke",
                      json={"tool": "calendar_get_upcoming_events",
                            "student_id": 1,
                            "arguments": {"days_ahead": 9999}}, timeout=40)
    check("out-of-range argument rejected (400)", r.status_code == 400,
          str(r.json().get("error")))
    r = requests.post(f"{BASE}/ai/mcp/invoke",
                      json={"tool": "calendar_get_upcoming_events",
                            "student_id": 1,
                            "arguments": {"days_ahead": 7, "delete": True}},
                      timeout=40)
    check("unexpected argument rejected (400)", r.status_code == 400,
          str(r.json().get("error")))
    r = requests.post(f"{BASE}/ai/mcp/invoke",
                      json={"tool": "calendar_get_upcoming_events",
                            "student_id": 1,
                            "arguments": {"days_ahead": "soon"}}, timeout=40)
    check("non-numeric argument rejected (400)", r.status_code == 400,
          str(r.json().get("error")))
    r = requests.post(f"{BASE}/ai/mcp/invoke",
                      json={"tool": "calendar_get_upcoming_events"}, timeout=40)
    check("missing student_id rejected (400)", r.status_code == 400,
          str(r.status_code))
    r = requests.post(f"{BASE}/ai/mcp/invoke",
                      json={"tool": "calendar_get_upcoming_events",
                            "student_id": 1,
                            "arguments": {"student_id": 2, "days_ahead": 60}},
                      timeout=40)
    check("student_id inside arguments cannot override the request's",
          r.status_code == 200, str(r.status_code))

    print("\n--- The calendar supplies its own documents to the RAG server ---")
    r = requests.post(f"{BASE}/ai/rag/ask",
                      json={"question": "When is my assignment due?",
                            "student_id": 1}, timeout=120)
    body = r.json()
    check("grounded answer returned", body.get("grounded") is True,
          str(body.get("answer") or body.get("error"))[:70])
    check("citations returned", len(body.get("citations", [])) > 0,
          str(len(body.get("citations", []))))
    # A "when is my assignment due" question is forward-looking, so it is
    # answered from what is still ahead. That is an assessment record, not the
    # past "Assignment 2 due" calendar event the old behaviour could pick.
    check("citation names a real record the calendar supplied",
          body["citations"][0]["source"].split(":")[0] in ("calendar", "assessment", "exam"),
          body["citations"][0]["source"])
    check("and it is not the overdue or completed one",
          body["citations"][0]["source"] not in ("assessment:2", "assessment:3", "assessment:5"),
          body["citations"][0]["source"])
    check("citation carries its supporting text",
          len(body["citations"][0]["snippet"]) > 20,
          body["citations"][0]["snippet"][:50])
    check("confidence category present",
          body.get("confidence") in ("high", "medium", "low"),
          str(body.get("confidence")))
    check("server's own label reported too",
          body.get("server_confidence") == "Context Available",
          str(body.get("server_confidence")))
    check("reports what was searched",
          body.get("searched", {}).get("documents", 0) > 0,
          str(body.get("searched")))

    print("\n--- Exams and assessments are searchable, not just calendar events ---")
    body = requests.post(f"{BASE}/ai/rag/ask",
                         json={"question": "When is my next exam?",
                               "student_id": 1}, timeout=120).json()
    check("exam question is answerable", body.get("grounded") is True,
          str(body.get("answer") or body.get("reason"))[:60])
    check("a cited source names the exam service",
          any(c["source"].startswith("exam:") for c in body.get("citations", [])),
          str([c["source"] for c in body.get("citations", [])]))

    searched = body.get("searched", {})
    check("documents drawn from more than the calendar",
          searched.get("assessment_documents", 0) > 0,
          str({k: v for k, v in searched.items() if k != "sources"}))

    print("\n--- Questions about the future are answered from what is still ahead ---")
    # The shared server ranks by shared words and knows nothing about dates, so
    # the calendar decides what it is shown. The model stub cites the first
    # record the server offers, so the cited record is the server's top choice.
    def add_lecture(days):
        r = requests.post(f"{BASE}/events", json={
            "student_id": 1, "subject": "30001", "title": "Statistics Lecture",
            "event_type": "lecture", "start_time": f"{ahead(days)} 10:00",
            "end_time": f"{ahead(days)} 11:30", "location": "CB02.01"}, timeout=20)
        return r.json().get("event_id")

    past_lecture, soon_lecture, later_lecture = add_lecture(-10), add_lecture(3), add_lecture(10)

    body = requests.post(f"{BASE}/ai/rag/ask",
                         json={"question": "When is my next lecture?",
                               "student_id": 1}, timeout=120).json()
    cited = [c["source"] for c in body.get("citations", [])]
    check("'next lecture' cites the soonest lecture still ahead",
          cited == [f"calendar:{soon_lecture}"],
          f"cited {cited}, soonest is calendar:{soon_lecture}")
    check("the later lecture was never offered to the server",
          f"calendar:{later_lecture}" not in cited and f"calendar:{past_lecture}" not in cited)
    searched = body.get("searched", {})
    check("the report says it was narrowed to the soonest match",
          searched.get("nearest_only") is True and searched.get("narrowed_to_next", 0) >= 1,
          str({k: v for k, v in searched.items() if k != "sources"}))

    body = requests.post(f"{BASE}/ai/rag/ask",
                         json={"question": "When is my assignment?",
                               "student_id": 1}, timeout=120).json()
    cited = [c["source"] for c in body.get("citations", [])]
    check("an assignment question cites an upcoming assignment",
          bool(cited) and set(cited) <= {"assessment:1", "assessment:4"}, str(cited))
    check("never the overdue one",
          "assessment:3" not in cited, str(cited))
    check("never one already completed",
          not ({"assessment:2", "assessment:5"} & set(cited)), str(cited))
    searched = body.get("searched", {})
    check("the report says what was left out",
          searched.get("upcoming_only") is True and searched.get("left_out", 0) >= 3,
          f"upcoming_only={searched.get('upcoming_only')} left_out={searched.get('left_out')}")

    body = requests.post(f"{BASE}/ai/rag/ask",
                         json={"question": "When was my last lecture?",
                               "student_id": 1}, timeout=120).json()
    check("a question about the past is not narrowed to the future",
          body.get("searched", {}).get("upcoming_only") is False,
          str(body.get("searched", {}).get("upcoming_only")))

    print("\n--- Confidence reflects how much of the question was covered ---")
    body = requests.post(f"{BASE}/ai/rag/ask",
                         json={"question": "When is my next lecture?",
                               "student_id": 1}, timeout=120).json()
    check("one cited record that covers the question is HIGH, not low",
          body.get("confidence") == "high", str(body.get("confidence")))
    check("the basis says why",
          "1 of 1 words" in (body.get("confidence_basis") or ""),
          str(body.get("confidence_basis")))
    check("the coverage is returned for the interface",
          body.get("coverage", {}).get("matched") == ["lecture"], str(body.get("coverage")))

    body = requests.post(f"{BASE}/ai/rag/ask",
                         json={"question": "When is my chemistry lecture?",
                               "student_id": 1}, timeout=120).json()
    check("a record that covers half of it is MEDIUM",
          body.get("confidence") == "medium", str(body.get("confidence")))
    check("and says what was not found",
          "not found: chemistry" in (body.get("confidence_basis") or ""),
          str(body.get("confidence_basis")))

    print("\n--- Insufficient context, not a guess ---")
    body = requests.post(f"{BASE}/ai/rag/ask",
                         json={"question": "What is the capital of France?",
                               "student_id": 1}, timeout=120).json()
    check("unrelated question is not grounded", body.get("grounded") is False,
          str(body.get("grounded")))
    check("confidence reported as insufficient",
          body.get("confidence") == "insufficient")
    check("explains that no answer was generated",
          "not enough relevant material" in (body.get("answer") or ""),
          (body.get("answer") or "")[:50])

    print("\n--- The model answering without citing is refused ---")
    MODE["ollama"] = "uncited"
    body = requests.post(f"{BASE}/ai/rag/ask",
                         json={"question": "When is my assignment due?",
                               "student_id": 1}, timeout=120).json()
    check("uncited answer is not grounded", body.get("grounded") is False,
          str(body.get("grounded")))
    check("unsupported claim not shown to the student",
          "definitely next Monday" not in (body.get("answer") or ""))

    print("\n--- The model's own refusal is honoured ---")
    MODE["ollama"] = "refuses"
    body = requests.post(f"{BASE}/ai/rag/ask",
                         json={"question": "When is my assignment due?",
                               "student_id": 1}, timeout=120).json()
    check("refusal returns insufficient context",
          body.get("grounded") is False)

    print("\n--- Ollama unavailable ---")
    MODE["ollama"] = "down"
    r = requests.post(f"{BASE}/ai/rag/ask",
                      json={"question": "When is my assignment due?",
                            "student_id": 1}, timeout=120)
    body = r.json()
    check("reported rather than crashing", "error" in body or "answer" in body)
    check("no answer invented", body.get("grounded") is not True,
          str(body.get("grounded")))
    MODE["ollama"] = "ok"

    print("\n--- Validation ---")
    check("missing question rejected",
          requests.post(f"{BASE}/ai/rag/ask",
                        json={"student_id": 1}, timeout=20).status_code == 400)
    check("missing student_id rejected",
          requests.post(f"{BASE}/ai/rag/ask",
                        json={"question": "x"}, timeout=20).status_code == 400)

    print("\n--- Release 0 functionality unaffected ---")
    events = requests.get(f"{BASE}/events", params={"student_id": 1},
                          timeout=20).json()
    check("calendar still serves its events", events.get("count", 0) > 0,
          str(events.get("count")))
    check("deadline import still works",
          requests.post(f"{BASE}/ai/find-deadlines", json={"student_id": 1},
                        timeout=60).status_code == 200)

finally:
    for p, _ in procs:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            p.wait(timeout=10)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass

print(f"\n{'=' * 58}\n  {sum(results)}/{len(results)} checks passed\n{'=' * 58}")
sys.exit(0 if all(results) else 1)
