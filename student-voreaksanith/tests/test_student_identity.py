
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
from itsdangerous import URLSafeTimedSerializer
from werkzeug.security import generate_password_hash

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAL = os.path.join(REPO, "student-voreaksanith")
AUTH_DIR = os.path.join(REPO, "shared", "backend")
MCP_DIR = os.path.join(REPO, "ai-services", "mcp-server")

HOST = "127.0.0.1"   # one host for every URL, so the session cookie is sent back
APP_PORT, MCP_PORT, AUTH_PORT, USERDB_PORT = 8000, 8011, 15911, 15903
APP = f"http://{HOST}:{APP_PORT}"
BASE = f"{APP}/calendar-api"
AUTH = f"http://{HOST}:{AUTH_PORT}"

LOGS = tempfile.gettempdir()
procs = {}
results = []


def check(label, ok, detail=""):
    results.append(ok)
    print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"  -- {detail}" if detail else ""))


USERS = {
    "amara@example.com": {"user_id": 1, "name": "Amara Osei",
                          "email": "amara@example.com",
                          "password": generate_password_hash("amara-pass")},
    "ben@example.com": {"user_id": 2, "name": "Ben Carter",
                        "email": "ben@example.com",
                        "password": generate_password_hash("ben-pass")},
}


class UserDb(BaseHTTPRequestHandler):
    """Stands in for the user database the auth service reads."""

    def log_message(self, *a): pass

    def do_GET(self):
        email = self.path.rsplit("/", 1)[-1]
        user = USERS.get(email)
        body = json.dumps(user if user else {"error": "not found"}).encode()
        self.send_response(200 if user else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)


threading.Thread(
    target=HTTPServer((HOST, USERDB_PORT), UserDb).serve_forever, daemon=True).start()


def start(name, cmd, cwd, env=None):
    p = subprocess.Popen(
        cmd, cwd=cwd, stdout=open(os.path.join(LOGS, f"identity_{name}.log"), "w"),
        stderr=subprocess.STDOUT, start_new_session=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1", **(env or {})})
    procs[name] = p
    return p


def stop(name):
    p = procs.pop(name, None)
    if not p:
        return
    try:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        p.wait(timeout=10)
    except Exception:
        try:
            p.kill()
        except Exception:
            pass


def wait(url, tries=70, method="get", **kw):
    for _ in range(tries):
        try:
            getattr(requests, method)(url, timeout=2, **kw)
            return True
        except requests.RequestException:
            time.sleep(0.5)
    return False


def login(email, password):
    s = requests.Session()
    r = s.post(f"{AUTH}/login", json={"email": email, "password": password}, timeout=15)
    return s, r


db = os.path.join(CAL, "database", "data", "calendar.db")
if os.path.exists(db):
    os.remove(db)

# The real auth service: the app is imported and run on a test port, because
# its own entry point is fixed to port 5000.
start("auth", [sys.executable, "-c",
               f"from app import create_app; create_app().run(host='{HOST}', port={AUTH_PORT})"],
      AUTH_DIR, {"DATABASE_SERVICE_URL": f"http://{HOST}:{USERDB_PORT}",
                 "AUTH_SECRET_KEY": "test-signing-key"})

# The real MCP server. Its calendar tool reads the calendar's database API.
start("mcp", [sys.executable, "server.py"], MCP_DIR,
      {"CALENDAR_DATABASE_URL": f"{APP}/db"})

# The real calendar backend, with the session check ON.
# MCP is switched on here, for this process only: the checks below call the
# calendar's MCP tool, and CI turns MCP off for the job as a whole.
start("calendar", [sys.executable, "run_local.py", str(APP_PORT), "--require-auth",
                   "--auth-url", AUTH, "--mcp-url", f"http://{HOST}:{MCP_PORT}/mcp"],
      CAL, {"MCP_ENABLED": "1", "RAG_ENABLED": "0"})

try:
    if not wait(f"{AUTH}/health"):
        print(open(os.path.join(LOGS, "identity_auth.log")).read()[-1500:])
        raise SystemExit("auth service did not start")
    if not wait(f"{APP}/"):
        print(open(os.path.join(LOGS, "identity_calendar.log")).read()[-1500:])
        raise SystemExit("calendar did not start")
    if not wait(f"http://{HOST}:{MCP_PORT}/mcp", method="post",
                headers={"Content-Type": "application/json",
                         "Accept": "application/json, text/event-stream"},
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}):
        print(open(os.path.join(LOGS, "identity_mcp.log")).read()[-1500:])
        raise SystemExit("MCP server did not start")

    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    print("\n--- no session: refused ---")
    check("events list refused (401)",
          requests.get(f"{BASE}/events", params={"student_id": 1}, timeout=20).status_code == 401)
    check("RAG question refused (401)",
          requests.post(f"{BASE}/ai/rag/ask", json={"question": "x", "student_id": 1},
                        timeout=20).status_code == 401)
    check("MCP call refused (401)",
          requests.post(f"{BASE}/ai/mcp/invoke",
                        json={"tool": "calendar_get_upcoming_events", "student_id": 1},
                        timeout=20).status_code == 401)
    check("diagnostics stays open for start-up checks",
          requests.get(f"{BASE}/ai/diagnostics", timeout=40).status_code == 200)

    print("\n--- signing in ---")
    amara, r = login("amara@example.com", "amara-pass")
    check("login succeeds", r.status_code == 200, str(r.status_code))
    cookie_header = r.headers.get("Set-Cookie", "")
    check("session cookie is HttpOnly", "HttpOnly" in cookie_header, cookie_header[:60])
    check("session cookie is SameSite=Lax", "SameSite=Lax" in cookie_header)
    check("login response still carries the user object (other features rely on it)",
          r.json().get("user", {}).get("user_id") == 1)
    ben, _ = login("ben@example.com", "ben-pass")
    _, bad = login("amara@example.com", "wrong")
    check("a wrong password gets no session",
          bad.status_code == 401 and "Set-Cookie" not in bad.headers, str(bad.status_code))
    check("/me names the signed-in student",
          amara.get(f"{AUTH}/me", timeout=10).json().get("user_id") == 1)

    print("\n--- a student acting as themselves ---")
    r = amara.get(f"{BASE}/events", params={"student_id": 1}, timeout=20)
    check("own events returned", r.status_code == 200 and r.json().get("count", 0) > 0,
          str(r.json().get("count")))
    r = amara.post(f"{BASE}/ai/mcp/invoke", json={
        "tool": "calendar_get_upcoming_events", "student_id": 1}, timeout=40)
    check("own MCP call allowed", r.status_code == 200, str(r.status_code))

    print("\n--- a student naming someone else: refused on every route ---")
    r = amara.get(f"{BASE}/events", params={"student_id": 2}, timeout=20)
    check("another student's events list (403)", r.status_code == 403, str(r.status_code))
    check("the refusal says why", "does not match" in r.json().get("error", ""),
          r.json().get("error"))
    check("creating an event for another student (403)",
          amara.post(f"{BASE}/events", json={
              "student_id": 2, "title": "x", "event_type": "other",
              "start_time": f"{tomorrow} 09:00", "end_time": f"{tomorrow} 10:00"},
              timeout=20).status_code == 403)
    check("MCP call for another student (403)",
          amara.post(f"{BASE}/ai/mcp/invoke", json={
              "tool": "calendar_get_upcoming_events", "student_id": 2},
              timeout=40).status_code == 403)
    check("RAG question about another student (403)",
          amara.post(f"{BASE}/ai/rag/ask", json={
              "question": "when is my exam", "student_id": 2},
              timeout=40).status_code == 403)
    check("study agent for another student (403)",
          amara.post(f"{BASE}/ai/suggest-schedule", json={"student_id": 2},
                     timeout=40).status_code == 403)
    check("deadline import for another student (403)",
          amara.post(f"{BASE}/ai/find-deadlines", json={"student_id": 2},
                     timeout=40).status_code == 403)
    check("briefing for another student (403)",
          amara.post(f"{BASE}/ai/briefing", json={"student_id": 2},
                     timeout=40).status_code == 403)

    print("\n--- forged and tampered sessions ---")
    forged = URLSafeTimedSerializer("some-other-key", salt="asd-session").dumps(
        {"user_id": 2, "name": "Ben Carter"})
    r = requests.get(f"{BASE}/events", params={"student_id": 2},
                     cookies={"asd_session": forged}, timeout=20)
    check("a token signed with a different key is refused (401)",
          r.status_code == 401, str(r.status_code))
    real = amara.cookies.get("asd_session")
    r = requests.get(f"{BASE}/events", params={"student_id": 1},
                     cookies={"asd_session": real[:-3] + "AAA"}, timeout=20)
    check("a tampered token is refused (401)", r.status_code == 401, str(r.status_code))
    r = requests.get(f"{BASE}/events", params={"student_id": 2},
                     headers={"Authorization": "Bearer not-a-token"}, timeout=20)
    check("a made-up bearer token is refused (401)", r.status_code == 401)

    print("\n--- events belong to the student who made them ---")
    r = amara.post(f"{BASE}/events", json={
        "student_id": 1, "title": "Amara private meeting", "event_type": "other",
        "start_time": f"{tomorrow} 09:00", "end_time": f"{tomorrow} 10:00"}, timeout=20)
    check("owner creates an event", r.status_code == 201, str(r.status_code))
    event_id = r.json().get("event_id")

    check("another student cannot read it (403)",
          ben.get(f"{BASE}/events/{event_id}", timeout=20).status_code == 403)
    check("another student cannot edit it (403)",
          ben.put(f"{BASE}/events/{event_id}", json={"title": "hijacked"},
                  timeout=20).status_code == 403)
    check("another student cannot move it (403)",
          ben.patch(f"{BASE}/events/{event_id}/move", json={"new_date": tomorrow},
                    timeout=20).status_code == 403)
    check("another student cannot delete it (403)",
          ben.delete(f"{BASE}/events/{event_id}", timeout=20).status_code == 403)
    r = amara.get(f"{BASE}/events/{event_id}", timeout=20)
    check("the event is untouched", r.status_code == 200
          and r.json().get("title") == "Amara private meeting", str(r.json().get("title")))
    check("a missing event is still a 404, not a 403",
          amara.get(f"{BASE}/events/999999", timeout=20).status_code == 404)

    print("\n--- the MCP tool under the session check ---")
    r = amara.post(f"{BASE}/ai/mcp/invoke", json={
        "tool": "calendar_get_upcoming_events", "student_id": 1,
        "arguments": {"days_ahead": 7}}, timeout=40)
    titles = [e["title"] for e in (r.json().get("result") or {}).get("events", [])]
    check("the owner's event comes back through MCP",
          "Amara private meeting" in titles, str(titles))

    r = ben.post(f"{BASE}/ai/mcp/invoke", json={
        "tool": "calendar_get_upcoming_events", "student_id": 2,
        "arguments": {"days_ahead": 7}}, timeout=40)
    titles = [e["title"] for e in (r.json().get("result") or {}).get("events", [])]
    check("another student's MCP result does not contain it",
          "Amara private meeting" not in titles, str(titles))

    r = ben.post(f"{BASE}/ai/mcp/invoke", json={
        "tool": "calendar_get_upcoming_events", "student_id": 2,
        "arguments": {"days_ahead": 7, "student_id": 1}}, timeout=40)
    titles = [e["title"] for e in (r.json().get("result") or {}).get("events", [])]
    check("a student_id hidden in the arguments cannot redirect the tool",
          r.status_code == 200 and "Amara private meeting" not in titles,
          f"{r.status_code} {titles}")

    print("\n--- signing out ---")
    r = amara.delete(f"{BASE}/events/{event_id}", timeout=20)
    check("the owner can delete their own event", r.status_code < 300, str(r.status_code))
    out = amara.post(f"{AUTH}/logout", timeout=10)
    check("logout succeeds", out.status_code == 200)
    check("the cookie is cleared", amara.cookies.get("asd_session") is None)
    check("the calendar then refuses the old session (401)",
          amara.get(f"{BASE}/events", params={"student_id": 1},
                    timeout=20).status_code == 401)

    print("\n--- the auth service is unavailable ---")
    time.sleep(1.2)   # a new login must produce a token the calendar has not cached
    fresh, _ = login("ben@example.com", "ben-pass")
    stop("auth")
    time.sleep(1)
    r = fresh.get(f"{BASE}/events", params={"student_id": 2}, timeout=30)
    check("a session that cannot be verified is refused, not allowed (503)",
          r.status_code == 503, str(r.status_code))
    check("the refusal names the sign-in service",
          "sign-in service" in r.json().get("error", ""), r.json().get("error"))

finally:
    for name in list(procs):
        stop(name)

print(f"\n{'=' * 58}\n  {sum(results)}/{len(results)} checks passed\n{'=' * 58}")
sys.exit(0 if all(results) else 1)
