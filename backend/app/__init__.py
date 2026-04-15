from flask import Flask, jsonify
from flask_cors import CORS

from .auth import auth_bp
from .config import Config
from .jobs import jobs_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(
        app,
        resources={r"/api/*": {"origins": [app.config["FRONTEND_ORIGIN"]]}},
        supports_credentials=False,
    )

    @app.get("/")
    def index():
        return jsonify(
            {
                "ok": True,
                "message": "Flask backend is running",
                "routes": [
                    "GET /api/health",
                    "GET /api/jobs",
                    "POST /api/auth/register",
                    "POST /api/auth/login",
                    "GET /api/auth/me",
                ],
            }
        )

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True, "message": "backend alive"})

    app.register_blueprint(auth_bp)
    app.register_blueprint(jobs_bp)
    return app
