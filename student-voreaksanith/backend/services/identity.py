"""Who is calling the calendar.

Before this, the backend trusted a student_id field sent by the browser, taken
from localStorage. Anyone could edit it and read or change another student's
events, or ask the AI features about them. Now:

  1. the shared auth service issues a signed session cookie at login
  2. this module asks that service who the cookie belongs to (GET /me)
  3. a request that names a different student is refused with 403
  4. a request for an event that belongs to someone else is refused with 403

install(app) adds the check as a before_request hook, so every calendar route
is covered without each route having to remember to call it.

The calendar does not hold the signing key. It asks the auth service rather
than verifying locally, so there is no shared secret to configure, and a
service that does not know the key cannot be tricked into trusting a forgery.
If the auth service cannot be reached the request is refused (503): failing
open would let anyone through exactly when the check cannot run.
"""
import time

import requests
from flask import g, jsonify, request

from config import (
    AUTH_CACHE_SECONDS,
    AUTH_COOKIE_NAME,
    AUTH_REQUIRED,
    AUTH_SERVICE_URL,
    AUTH_TIMEOUT_SECONDS,
)
from services import calendar_service

# Reachable without a session. Diagnostics is read by start-up scripts and by
# people checking why a panel is empty, before any one is signed in.
OPEN_PATHS = {"/ai/diagnostics"}

_verified = {}   # token -> (expires_at, user)


class AuthUnavailable(Exception):
    """The auth service could not be reached or answered unexpectedly."""


def _token():
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if token:
        return token

    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()

    return None


def who_is(token):
    """The user this token belongs to, or None if it does not verify."""
    now = time.time()

    cached = _verified.get(token)
    if cached and cached[0] > now:
        return cached[1]

    try:
        response = requests.get(
            f"{AUTH_SERVICE_URL.rstrip('/')}/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=AUTH_TIMEOUT_SECONDS,
        )
    except requests.RequestException as error:
        raise AuthUnavailable(type(error).__name__) from error

    if response.status_code == 401:
        _verified.pop(token, None)
        return None

    if response.status_code != 200:
        raise AuthUnavailable(f"auth service returned {response.status_code}")

    user = response.json()
    if AUTH_CACHE_SECONDS > 0:
        _verified[token] = (now + AUTH_CACHE_SECONDS, user)
        # Keep the cache from growing without bound.
        if len(_verified) > 1000:
            _verified.clear()

    return user


def _claimed_student_id():
    """The student id this request says it is acting for, if it names one."""
    claimed = request.args.get("student_id")
    if claimed not in (None, ""):
        return claimed

    body = request.get_json(silent=True)
    if isinstance(body, dict) and body.get("student_id") not in (None, ""):
        return body.get("student_id")

    return None


def check_request():
    """before_request hook. Returns a response to refuse, or None to allow."""
    if not AUTH_REQUIRED:
        return None

    if request.method == "OPTIONS" or request.path in OPEN_PATHS:
        return None

    token = _token()
    if not token:
        return jsonify({"error": "Sign in required"}), 401

    try:
        user = who_is(token)
    except AuthUnavailable as error:
        return jsonify({
            "error": f"The sign-in service is unavailable ({error})"
        }), 503

    if user is None:
        return jsonify({"error": "Your session has expired. Sign in again."}), 401

    g.student_id = int(user["user_id"])

    claimed = _claimed_student_id()
    if claimed is not None and str(claimed).strip() != str(g.student_id):
        return jsonify({
            "error": "student_id does not match the signed-in student"
        }), 403

    # Routes addressed by event id carry no student_id, so ownership has to be
    # checked against the stored event. A missing event falls through to the
    # route, which reports the 404 itself.
    event_id = (request.view_args or {}).get("event_id")
    if event_id is not None:
        status_code, event = calendar_service.get_event(event_id)
        if status_code == 200 and str(event.get("student_id")) != str(g.student_id):
            return jsonify({
                "error": "That event belongs to another student"
            }), 403

    return None


def install(app):
    app.before_request(check_request)
