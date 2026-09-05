from pathlib import Path
import sys

from flask import Flask
from flask_cors import CORS


BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from routes.ai_mode import ai_mode_bp

from routes.health_routes import health_bp

from routes.exams import (
    get_exam_bp,
    post_exam_bp,
    put_exam_bp,
    delete_exam_bp,
)


def create_app():
    app = Flask(__name__)
    CORS(app)

    app.register_blueprint(health_bp)

    app.register_blueprint(get_exam_bp)
    app.register_blueprint(post_exam_bp)
    app.register_blueprint(put_exam_bp)
    app.register_blueprint(delete_exam_bp)
    
    app.register_blueprint(ai_mode_bp)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5009, debug=True)