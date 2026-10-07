"""Tests for the shared RAG server.

Stub feature services supply the data, and a stub Ollama supplies the wording,
so every path can be exercised without the full stack or a real model.

The cases that matter most are the ones about grounding: an unrelated question
must return insufficient context rather than the least-bad passage, and a
model that ignores its instructions must not produce an unsupported answer.
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

HERE = os.path.dirname(os.path.abspath(__file__))
RAG_PORT = 15700
OLLAMA_PORT = 15702
BASE = f"http://127.0.0.1:{RAG_PORT}"

PORTS = {"enrolment": 15710, "notebook": 15712,
         "calendar": 15714, "assessment": 15716, "exam": 15718}

IS_WINDOWS = os.name == "nt"
SPAWN = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if IS_WINDOWS
         else {"start_new_session": True})
LOG = os.path.join(tempfile.gettempdir(), "rag_server_test.log")

results = []


def check(label, ok, detail=""):
    results.append(ok)
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  -- {detail}" if detail else ""))


MODE = {"ollama": "ok"}
DOWN = set()

DATA = {
    "exam": {"/exams": [
        {"exam_id": 1, "student_id": 1, "course_id": 101,
         "exam_name": "ASD101 Final Examination", "exam_date": "2026-10-10",
         "exam_time": "09:00", "status": "Uncompleted"}]},
    "assessment": {"/assignments": [
        {"assignment_id": 1, "student_id": 1, "course_id": 41026,
         "title": "Software Architecture Report", "due_date": "2026-09-20",
         "weighting": 35, "status": "in_progress",
         "description": "Document the integrated architecture."}]},
    "calendar": {"/events": [
        {"event_id": 1, "student_id": 1, "subject": "41026",
         "title": "ASD Lecture", "event_type": "lecture",
         "start_time": "2026-09-02 10:00", "location": "CB11.05.300"}]},
    "enrolment": {
        "/courses": [{"course_id": 1, "course_code": "41026",
                      "course_name": "Advanced Software Development",
                      "description": "Software development with Agent AI."}],
        "/enrolments": [{"enrolment_id": 1, "student_id": 1, "course_id": 1,
                         "enrolment_status": "enrolled",
                         "enrolment_date": "2026-08-22"}]},
    "notebook": {
        "/notebooks": [{"notebook_id": 1, "notebook_title": "ASD Notes"}],
        "/notebooks/1/notes": [
            {"note_id": 1, "note_title": "Docker Compose",
             "note_content": "Docker Compose builds and starts every container "
                             "as one application."}]},
}


def make_handler(service):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            if service in DOWN:
                self.send_response(503); self.end_headers(); return
            payload = DATA[service].get(self.path.split("?")[0])
            if payload is None:
                self.send_response(404); self.end_headers(); return
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body)
    return H


class OllamaStub(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        if MODE["ollama"] == "down":
            self.send_response(503); self.end_headers(); return

        n = int(self.headers.get("Content-Length", 0))
        prompt = json.loads(self.rfile.read(n))["messages"][-1]["content"]

        if MODE["ollama"] == "refuses":
            content = "INSUFFICIENT_CONTEXT"
        elif MODE["ollama"] == "echo_context":
            # Answers using only what it was given, as instructed.
            first = prompt.split("[1]")[1].split("[2]")[0] if "[1]" in prompt else ""
            content = first.strip().split("\n", 1)[-1][:160]
        else:
            content = ("Your ASD101 Final Examination is on 10 October 2026 "
                       "at 09:00.")

        body = json.dumps({"message": {"content": content}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)


for name, port in PORTS.items():
    HTTPServer(("127.0.0.1", port), make_handler(name))
servers = []
for name, port in PORTS.items():
    s = HTTPServer(("127.0.0.1", port), make_handler(name))
    threading.Thread(target=s.serve_forever, daemon=True).start()
    servers.append(s)

ollama = HTTPServer(("127.0.0.1", OLLAMA_PORT), OllamaStub)
threading.Thread(target=ollama.serve_forever, daemon=True).start()

proc = subprocess.Popen(
    [sys.executable, "app.py"], cwd=HERE,
    stdout=open(LOG, "w"), stderr=subprocess.STDOUT, **SPAWN,
    env={**os.environ, "PYTHONUNBUFFERED": "1",
         "RAG_PORT": str(RAG_PORT),
         "OLLAMA_BASE_URL": f"http://127.0.0.1:{OLLAMA_PORT}",
         "OLLAMA_MODEL": "stub-model",
         "ENROLMENT_DB_URL": f"http://127.0.0.1:{PORTS['enrolment']}",
         "NOTEBOOK_DB_URL": f"http://127.0.0.1:{PORTS['notebook']}",
         "CALENDAR_DB_URL": f"http://127.0.0.1:{PORTS['calendar']}",
         "ASSESSMENT_DB_URL": f"http://127.0.0.1:{PORTS['assessment']}",
         "EXAM_DB_URL": f"http://127.0.0.1:{PORTS['exam']}",
         "RAG_UPSTREAM_TIMEOUT": "5"})


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
for _ in range(60):
    try:
        requests.get(f"{BASE}/health", timeout=2); up = True; break
    except requests.RequestException:
        time.sleep(0.4)


def ask(question, **extra):
    return requests.post(f"{BASE}/query",
                         json={"question": question, **extra}, timeout=60)


try:
    if not up:
        print(open(LOG).read()[-2000:]); raise SystemExit("RAG server did not start")

    print("\n--- Index is built from the project's own data ---")
    h = requests.get(f"{BASE}/health", timeout=20).json()
    check("server healthy", h.get("status") == "ok")
    check("passages indexed", h["passages"] > 5, str(h["passages"]))
    sources = h["index"]["sources"]
    check("exams indexed", sources.get("exams") == 1, str(sources.get("exams")))
    check("assignments indexed", sources.get("assignments") == 1)
    check("notes indexed", sources.get("notes") == 1)
    check("shipped documents indexed", sources.get("documents", 0) > 3,
          str(sources.get("documents")))

    print("\n--- A grounded answer carries sources and a confidence level ---")
    r = ask("When is my exam?")
    body = r.json()
    check("answer is grounded", body.get("grounded") is True)
    check("answer returned", len(body.get("answer") or "") > 15,
          (body.get("answer") or "")[:50])
    check("citations returned", len(body.get("citations", [])) > 0,
          str(len(body.get("citations", []))))
    check("top citation is the student's own exam record",
          "exam timetable" in body["citations"][0]["source"],
          body["citations"][0]["source"])
    check("confidence category returned",
          body.get("confidence") in ("high", "medium", "low"),
          str(body.get("confidence")))

    print("\n--- Retrieval finds the right record ---")
    body = ask("What is the Software Architecture Report worth?").json()
    top = body["citations"][0]["source"]
    check("assignment question retrieves the assignment", "assignment" in top, top)
    check("retrieved passage carries the weighting",
          "35" in body["citations"][0]["snippet"],
          body["citations"][0]["snippet"][:60])

    body = ask("What does Docker Compose do?").json()
    sources_hit = [c["source"] for c in body["citations"]]
    check("note question retrieves a note or document",
          any("note" in s or ".md" in s for s in sources_hit), str(sources_hit[:2]))

    print("\n--- Insufficient context, not a guess ---")
    body = ask("What is the capital of France?").json()
    check("unrelated question is not grounded", body.get("grounded") is False)
    check("insufficient flag set", body.get("insufficient_context") is True)
    check("confidence reported as insufficient",
          body.get("confidence") == "insufficient")
    check("no citations claimed", body.get("citations") == [])
    check("explains why", "not enough relevant material" in body.get("answer", ""))

    print("\n--- The model's own refusal is honoured ---")
    MODE["ollama"] = "refuses"
    body = ask("When is my exam?").json()
    check("refusal returns insufficient context", body.get("grounded") is False,
          str(body.get("grounded")))
    check("refusal token is not shown to the student",
          "INSUFFICIENT_CONTEXT" not in (body.get("answer") or ""))
    check("retrieved citations still reported",
          len(body.get("citations", [])) > 0)

    print("\n--- Ollama unavailable: still grounded, no invention ---")
    MODE["ollama"] = "down"
    body = ask("When is my exam?").json()
    check("answer still returned", len(body.get("answer") or "") > 15)
    check("still grounded", body.get("grounded") is True)
    check("marked as not generated", body.get("generated") is False)
    check("answer comes from the indexed passage",
          "2026-10-10" in body.get("answer", ""), body.get("answer", "")[:60])
    check("says why it was not written up", "model unavailable" in
          (body.get("note") or ""), str(body.get("note"))[:60])
    MODE["ollama"] = "ok"

    print("\n--- Validation and reindexing ---")
    r = requests.post(f"{BASE}/query", json={}, timeout=20)
    check("missing question rejected", r.status_code == 400)
    r = requests.post(f"{BASE}/reindex", json={}, timeout=30)
    check("reindex succeeds", r.json().get("reindexed") is True)

    print("\n--- A feature service being unavailable ---")
    DOWN.add("exam")
    r = requests.post(f"{BASE}/reindex", json={}, timeout=30).json()
    check("index still builds", r["index"]["passages"] > 0,
          str(r["index"]["passages"]))
    check("unavailable source reported",
          any(u["source"] == "exams" for u in r["index"]["unavailable"]),
          str(r["index"]["unavailable"]))
    body = ask("What is the Software Architecture Report worth?").json()
    check("other sources still answer", body.get("grounded") is True)
    DOWN.clear()

finally:
    stop(proc)

print(f"\n{'=' * 58}\n  {sum(results)}/{len(results)} checks passed\n{'=' * 58}")
sys.exit(0 if all(results) else 1)
