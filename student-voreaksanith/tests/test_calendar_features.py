"""Calendar feature tests.

Exercises add/delete/move, the deadline import, the weighting-aware planner
and the daily briefing against stub assessment, exam and Ollama services, so
the suite runs in CI without those services or a model being installed.

Stubs stand in for the other teams' services so every path can be exercised,
including one or both being unreachable.
"""
import json, os, signal, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

CAL = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Written to the system temp directory so the suite runs on Windows as well as
# Linux; "/tmp" does not exist on Windows.
SERVER_LOG = os.path.join(tempfile.gettempdir(), "calendar_test_server.log")

# Popen and process termination differ between platforms. On Windows there are
# no process groups in the POSIX sense, so the child is started in its own
# group and terminated directly.
IS_WINDOWS = os.name == "nt"
SPAWN_KWARGS = (
    {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if IS_WINDOWS
    else {"start_new_session": True}
)


def stop(process):
    """Terminate a spawned server on either platform."""
    try:
        if IS_WINDOWS:
            process.terminate()
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process.wait(timeout=10)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass
PORT, ASSESS_PORT, EXAM_PORT, OLLAMA_PORT = 8000, 15008, 15010, 11500
BASE = f"http://localhost:{PORT}/calendar-api"

results = []
def check(label, ok, detail=""):
    results.append(ok)
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  -- {detail}" if detail else ""))

ASSIGNMENTS = [
    {"assignment_id": 1, "student_id": 1, "course_id": 41026,
     "title": "Software Architecture Report", "due_date": "2026-09-20",
     "weighting": 35, "status": "in_progress"},
    {"assignment_id": 2, "student_id": 1, "course_id": 31271,
     "title": "Database Assignment", "due_date": "2026-09-15",
     "weighting": 10, "status": "not_started"},
    {"assignment_id": 3, "student_id": 1, "course_id": 48024,
     "title": "Web Development Project", "due_date": "2026-09-28",
     "weighting": 40, "status": "not_started"},
    {"assignment_id": 4, "student_id": 1, "course_id": 41026,
     "title": "Done Already", "due_date": "2026-09-14",
     "weighting": 5, "status": "completed"},
    # Same title as a seeded calendar event -> must be detected as duplicate.
    {"assignment_id": 5, "student_id": 1, "course_id": 41026,
     "title": "Assignment 2 due", "due_date": "2026-09-25",
     "weighting": 20, "status": "not_started"},
]
EXAMS = [
    {"exam_id": 1, "course_id": 101, "student_id": 1,
     "exam_name": "ASD101 Final Exam", "exam_date": "2026-10-10",
     "exam_time": "09:00", "status": "Uncompleted"},
    {"exam_id": 2, "course_id": 201, "student_id": 9999,
     "exam_name": "Someone Else Exam", "exam_date": "2026-10-12",
     "exam_time": "13:00", "status": "Uncompleted"},
]

STATE = {"assess_up": True, "exam_up": True}


def make_handler(kind):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            up = STATE["assess_up"] if kind == "assess" else STATE["exam_up"]
            if not up:
                self.send_response(503); self.end_headers(); return
            data = ASSIGNMENTS if kind == "assess" else EXAMS
            if kind == "assess" and "student_id=" in self.path:
                sid = self.path.split("student_id=")[1].split("&")[0]
                data = [a for a in data if str(a["student_id"]) == sid]
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body)
    return H


class Ollama(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        self.rfile.read(n)
        body = json.dumps({"message": {"content":
            "You have two classes today. Your Web Development Project is the "
            "one to start on."}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)


servers = []
for port, h in [(ASSESS_PORT, make_handler("assess")),
                (EXAM_PORT, make_handler("exam")), (OLLAMA_PORT, Ollama)]:
    s = HTTPServer(("127.0.0.1", port), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    servers.append(s)

db = os.path.join(CAL, "database/data/calendar.db")
if os.path.exists(db):
    os.remove(db)

proc = subprocess.Popen(
    [sys.executable, "run_local.py", str(PORT)], cwd=CAL,
    stdout=open(SERVER_LOG, "w"), stderr=subprocess.STDOUT,
    **SPAWN_KWARGS,
    env={**os.environ, "PYTHONUNBUFFERED": "1",
         "ASSESSMENT_SERVICE_URL": f"http://127.0.0.1:{ASSESS_PORT}",
         "EXAM_SERVICE_URL": f"http://127.0.0.1:{EXAM_PORT}",
         "OLLAMA_BASE_URL": f"http://127.0.0.1:{OLLAMA_PORT}",
         "OLLAMA_MODEL": "stub"})

up = False
for _ in range(50):
    try:
        requests.get(f"http://localhost:{PORT}/", timeout=1); up = True; break
    except requests.RequestException:
        time.sleep(0.4)

REQ = {"student_id": 1, "from_date": "2026-09-01 08:00"}

try:
    if not up:
        print(open(SERVER_LOG).read()[-2500:]); raise SystemExit("no server")

    print("\n--- COURSES REMOVED ---")
    r = requests.get(f"{BASE}/events", params={"student_id": 1}).json()
    ev = r["events"][0]
    check("no course_code/course_name on events",
          "course_code" not in ev and "course_name" not in ev, str(list(ev.keys())))
    check("subject label kept instead", ev.get("subject") == "41026", str(ev.get("subject")))
    check("/calendar/courses endpoint gone",
          requests.get(f"{BASE}/courses", params={"student_id": 1}).status_code == 404)

    print("\n--- FEATURE 1: find deadlines not yet on the calendar ---")
    f = requests.post(f"{BASE}/ai/find-deadlines", json=REQ).json()
    titles = [m["title"] for m in f["missing"]]
    check("pulls from assessments service",
          "Software Architecture Report" in titles, str(titles))
    check("pulls from exams service", "ASD101 Final Exam" in titles)
    check("excludes other students' exams", "Someone Else Exam" not in titles)
    check("detects duplicate already on calendar",
          "Assignment 2 due" not in titles and f["already_in_calendar"] >= 1,
          f"already={f['already_in_calendar']}")
    check("completed assignment NOT offered for import",
          "Done Already" not in titles and f.get("completed_skipped", 0) >= 1,
          f"completed_skipped={f.get('completed_skipped')}")
    check("exam typed as exam, assignment as deadline",
          all(m["event_type"] == ("exam" if m["source"] == "exam" else "deadline")
              for m in f["missing"]))
    check("reports source availability",
          f["sources"]["assessments"]["available"] and f["sources"]["exams"]["available"])

    before = requests.get(f"{BASE}/events", params={"student_id": 1}).json()["count"]
    check("nothing written by the preview", before == 8, f"{before} events")

    print("\n--- FEATURE 1: import ---")
    imp = requests.post(f"{BASE}/ai/import-deadlines",
                        json={"student_id": 1, "items": f["missing"]}).json()
    check("creates the events", imp["created_count"] == len(f["missing"]),
          f"{imp['created_count']} of {len(f['missing'])}")
    after = requests.get(f"{BASE}/events", params={"student_id": 1}).json()["count"]
    check("events persisted", after == before + imp["created_count"], f"{after}")

    again = requests.post(f"{BASE}/ai/find-deadlines", json=REQ).json()
    check("re-running finds nothing new (idempotent)",
          again["missing_count"] == 0, f"{again['missing_count']} missing")

    dup = requests.post(f"{BASE}/ai/import-deadlines",
                        json={"student_id": 1, "items": f["missing"]}).json()
    check("re-importing skips duplicates",
          dup["created_count"] == 0 and len(dup["skipped_duplicates"]) > 0,
          f"created={dup['created_count']}")

    print("\n--- FEATURE 2: weighting-aware ranking ---")
    sch = requests.post(f"{BASE}/ai/suggest-schedule", json=REQ, timeout=60).json()
    ranking = sch["trace"]["plan"]["ranking"]
    check("ranking recorded in trace", len(ranking) > 0, f"{len(ranking)} targets")
    check("ranked by weighting per day", sch["trace"]["plan"]["ranked_by"].startswith("weighting"))
    weighted = [r for r in ranking if (r.get("weighting") or 0) > 0]
    check("weightings pulled from assessments", len(weighted) >= 3, f"{len(weighted)} weighted")
    # 40% due 28 Sept should outrank 10% due 15 Sept
    order = [r["title"] for r in ranking]
    if "Web Development Project" in order and "Database Assignment" in order:
        check("40% item outranks 10% item despite later due date",
              order.index("Web Development Project") < order.index("Database Assignment"),
              f"{order[:3]}")
    check("suggestions produced", len(sch["suggestions"]) > 0, f"{len(sch['suggestions'])}")

    print("\n--- FEATURE 4: daily briefing ---")
    b = requests.post(f"{BASE}/ai/briefing", json=REQ, timeout=60).json()
    facts = b["facts"]
    check("summary returned", bool(b["summary"]), b["summary"][:60])
    check("today's events listed", isinstance(facts["events_today"], list))
    check("due-this-week computed", isinstance(facts["due_this_week"], list),
          f"{len(facts['due_this_week'])} items")
    check("next exam identified",
          facts["next_exam"] and "ASD101" in facts["next_exam"]["title"],
          str(facts["next_exam"]))
    check("priorities ranked by urgency",
          [p["urgency"] for p in facts["top_priorities"]] ==
          sorted([p["urgency"] for p in facts["top_priorities"]], reverse=True))
    check("completed work excluded",
          all("Done Already" != p["title"] for p in facts["top_priorities"]))
    check("trace explains figures are computed", "computed" in b["trace"]["reasoning"])

    print("\n--- DEGRADATION: assessment service down ---")
    STATE["assess_up"] = False
    d = requests.post(f"{BASE}/ai/find-deadlines", json=REQ, timeout=30).json()
    check("still responds", "missing" in d)
    check("marks assessments unavailable", d["sources"]["assessments"]["available"] is False)
    check("exams still read", d["sources"]["exams"]["available"] is True)
    b2 = requests.post(f"{BASE}/ai/briefing", json=REQ, timeout=60).json()
    check("briefing still works", bool(b2["summary"]))

    print("\n--- DEGRADATION: both sources + Ollama down ---")
    STATE["exam_up"] = False
    for s in servers[2:]:
        s.shutdown(); s.server_close()
    time.sleep(1)
    b3 = requests.post(f"{BASE}/ai/briefing", json=REQ, timeout=60).json()
    check("briefing falls back without llm", bool(b3["summary"]),
          b3["summary"][:70])
    check("fallback flagged in trace", b3["trace"]["llm_invoked"] is False)
    check("calendar events still served",
          requests.get(f"{BASE}/events", params={"student_id": 1}).status_code == 200)

    print("\n--- VALIDATION ---")
    check("find-deadlines needs student_id",
          requests.post(f"{BASE}/ai/find-deadlines", json={}).status_code == 400)
    check("import needs items",
          requests.post(f"{BASE}/ai/import-deadlines",
                        json={"student_id": 1}).status_code == 400)
    check("briefing needs student_id",
          requests.post(f"{BASE}/ai/briefing", json={}).status_code == 400)

finally:
    stop(proc)

print(f"\n{'='*58}\n  {sum(results)}/{len(results)} checks passed\n{'='*58}")
sys.exit(0 if all(results) else 1)
