from flask import Flask, jsonify, request
from flask_cors import CORS

from app.domains.auth.router import auth_bp
from app.domains.jobs.assistant import jobs_assistant_bp
from app.domains.jobs.router import jobs_bp
from app.domains.match.router import match_bp
from app.domains.personality.router import personality_bp
from app.domains.profile.router import portrait_bp
from app.core.errors import register_error_handlers
from app.domains.report.router import career_report_bp
from app.core.config import Config


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["MAX_CONTENT_LENGTH"] = Config.MAX_UPLOAD_MB * 1024 * 1024
    register_error_handlers(app)

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        if app.config.get("API_CACHE_NO_STORE", True) and request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
        return response

    CORS(
        app,
        resources={r"/api/*": {"origins": [app.config["FRONTEND_ORIGIN"]]}},
        supports_credentials=False,
    )

    app.register_blueprint(portrait_bp)
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
                    "GET /api/profile/resumes",
                    "POST /api/match/preview",
                    "POST /api/report/targets/import-from-match",
                    "POST /api/report/targets/manual-search",
                    "POST /api/report/generate",
                    "POST /api/report/<report_id>/enrich",
                    "POST /api/report/track-public-info",
                    "GET /api/report/my/list",
                    "GET /api/report/:id",
                    "GET /api/report/:id/reviews",
                    "POST /api/report/review-cycle",
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
    app.register_blueprint(career_report_bp)
    return app
