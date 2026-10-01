from flask import Blueprint, jsonify


health_bp = Blueprint(
    "health",
    __name__
)


# ==================================================
# HEALTH CHECK
# ==================================================

@health_bp.get("/")
def health():

    return jsonify({
        "service": "exam-backend",
        "status": "running"
    }), 200