from flask import Flask

from routes.normal_ui import normal_ui_bp
from routes.ai_mode import ai_mode_bp


app = Flask(__name__)

app.register_blueprint(normal_ui_bp)
app.register_blueprint(ai_mode_bp)


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
        use_reloader=False
    )