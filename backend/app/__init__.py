from flask import Flask, jsonify
from flask_cors import CORS

from .auth import auth_bp
from .config import Config
from .jobs import jobs_bp
from .jobs_assistant import jobs_assistant_bp
from .match_preview import match_bp
from .mock_capability_profiles import mock_profile_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(
        app,
        resources={r"/api/*": {"origins": [app.config["FRONTEND_ORIGIN"]]}},
        supports_credentials=False,
    )
    from .profile import portrait_bp

    app.register_blueprint(mock_profile_bp)
    app.register_blueprint(portrait_bp)
    from .personality import personality_bp
    app.register_blueprint(personality_bp)
    @app.get("/")
    def index():
        return jsonify(
            {
                "ok": True,
                "message": "Flask backend is running",
                "routes": [
                    "GET /api/health",
                    "GET /api/jobs",
                    "POST /api/jobs/assistant/chat",
                    "POST /api/auth/register",
                    "POST /api/auth/login",
                    "GET /api/auth/me",
                    "GET /api/personality/questions",
                    "POST /api/personality/submit",
                    "GET /api/profile/mocks",
                    "POST /api/match/preview",
                ],
            }
        )

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True, "message": "backend alive"})

    app.register_blueprint(auth_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(jobs_assistant_bp)
    app.register_blueprint(match_bp)
    return app
