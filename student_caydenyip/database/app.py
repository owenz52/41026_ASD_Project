from flask import Flask
from flask_cors import CORS

from routes import (
    get_exam_bp,
    post_exam_bp,
    put_exam_bp,
    delete_exam_bp,
    reset_exam_bp,
    sync_exam_bp,
)


def create_app():

    app = Flask(__name__)

    CORS(app)

    app.register_blueprint(get_exam_bp)
    app.register_blueprint(post_exam_bp)
    app.register_blueprint(put_exam_bp)
    app.register_blueprint(delete_exam_bp)
    app.register_blueprint(reset_exam_bp)
    app.register_blueprint(sync_exam_bp)

    return app


app = create_app()


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5010,
        debug=True
    )
