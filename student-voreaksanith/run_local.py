"""Run the calendar on one port, in one window (local development only).

Mounts the backend API, the calendar database service and the frontend behind
a single port so there is no need for several terminals:

    /               the calendar page
    /calendar/...   the backend API
    /db/...         the calendar database service

Docker still runs these as separate containers; nothing here changes that.

    python run_local.py          # http://localhost:8000
    python run_local.py 9000     # a different port
"""
import importlib.util
import os
import sys
from pathlib import Path

CAL_DIR = Path(__file__).resolve().parent
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    if not (CAL_DIR / "backend" / "app.py").exists():
        sys.exit(f"Run this from inside the calendar folder. Currently: {CAL_DIR}")

    if not (CAL_DIR / "database" / "data" / "calendar.db").exists():
        print("Seeding calendar database...")
        load_module("_cal_init", CAL_DIR / "database" / "init_db.py").init_db()

    base = f"http://127.0.0.1:{PORT}"
    os.environ["DATABASE_SERVICE_URL"] = f"{base}/db"

    sys.path.insert(0, str(CAL_DIR / "backend"))

    from flask import Flask, send_from_directory
    from flask_cors import CORS
    from werkzeug.middleware.dispatcher import DispatcherMiddleware
    from werkzeug.serving import run_simple

    from routes.ai_mode import ai_mode_bp
    from routes.calendar_routes import calendar_bp

    frontend_dir = CAL_DIR / "frontend"

    app = Flask(__name__, static_folder=None)
    CORS(app)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(ai_mode_bp)

    @app.route("/")
    def index():
        return send_from_directory(frontend_dir, "index.html")

    @app.route("/<path:filename>")
    def static_files(filename):
        return send_from_directory(frontend_dir, filename)

    cal_db = load_module("_cal_db", CAL_DIR / "database" / "app.py")
    application = DispatcherMiddleware(app, {"/db": cal_db.app})

    def rewrite_api_prefix(wsgi_app):
        """Strip the /calendar-api prefix, as the portal's nginx does.

        The API routes are registered at root to match every other backend in
        the project; the portal proxies /calendar-api/ to the backend root.
        """
        def middleware(environ, start_response):
            path = environ.get("PATH_INFO", "")
            if path.startswith("/calendar-api/"):
                environ["PATH_INFO"] = "/" + path[len("/calendar-api/"):]
            return wsgi_app(environ, start_response)
        return middleware

    application = rewrite_api_prefix(application)

    print()
    print("=" * 56)
    print(f"  Calendar running at  http://localhost:{PORT}")
    print("=" * 56)
    print(f"  page  http://localhost:{PORT}/")
    print(f"  API   http://localhost:{PORT}/calendar/events?student_id=1001")
    print("  Press CTRL+C to stop")
    print()

    try:
        # threaded=True is required: the backend makes HTTP calls back to this
        # same server, which would deadlock a single-threaded process.
        run_simple("0.0.0.0", PORT, application,
                   threaded=True, use_reloader=False, use_debugger=True)
    except OSError as error:
        if getattr(error, "errno", None) in (48, 98, 10048):
            sys.exit(f"\nPort {PORT} is in use. Try: python run_local.py 8001")
        raise


if __name__ == "__main__":
    main()
