from pathlib import Path
import sys

from flask import Flask
from flask_cors import CORS

BASE_DIR = Path(__file__).resolve().parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from routes.auth import auth_bp


def create_app():
    app = Flask(__name__)
    CORS(app)

    app.register_blueprint(auth_bp)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)