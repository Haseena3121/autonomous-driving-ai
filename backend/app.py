"""Flask application for the AI-Based Autonomous Driving System (ADAS).

Run with:
    python app.py            # http://localhost:5000

The user-trained YOLO model (backend/models/best.pt) is loaded exactly once,
at startup. If the weights file is missing the server still starts, reports
the problem through /api/health and /api/model/info, and every inference
endpoint returns HTTP 503 — no fake or placeholder model is ever substituted.
"""

import logging
import threading
import time
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

import config
from routes import core_routes, detection_routes, tracking_routes, lane_routes, depth_routes, simulation_routes, chat_routes, auth_routes
from services import model_service

logger = logging.getLogger("adas")


def _configure_logging() -> None:
    """Console + rotating file logging for every module."""
    formatter = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    root.addHandler(stream)
    try:
        file_handler = RotatingFileHandler(config.LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:  # read-only filesystem: console logging still works
        pass


def _register_error_handlers(app: Flask) -> None:
    def error_body(code: str, message: str):
        return jsonify({"success": False, "error": {"code": code, "message": message}})

    @app.errorhandler(400)
    def bad_request(err):
        return error_body("INVALID_REQUEST", err.description or "Bad request."), 400

    @app.errorhandler(404)
    def not_found(err):
        return error_body("NOT_FOUND", "The requested resource does not exist."), 404

    @app.errorhandler(405)
    def method_not_allowed(err):
        return error_body("METHOD_NOT_ALLOWED", "HTTP method not allowed for this endpoint."), 405

    @app.errorhandler(413)
    def too_large(err):
        return (
            error_body("FILE_TOO_LARGE", f"Upload exceeds the {config.MAX_VIDEO_MB} MB limit."),
            413,
        )

    @app.errorhandler(Exception)
    def unexpected(err):
        if isinstance(err, HTTPException):
            return error_body("HTTP_ERROR", err.description or err.name), err.code or 500
        logger.exception("Unhandled server error")
        return error_body("INTERNAL_ERROR", "An unexpected server error occurred. See backend/app.log."), 500


def _cleanup_loop(app: Flask) -> None:
    """Daemon thread: delete uploads/outputs older than CLEANUP_MAX_AGE_HOURS."""
    max_age = config.CLEANUP_MAX_AGE_HOURS * 3600
    while True:
        time.sleep(config.CLEANUP_INTERVAL_SECONDS)
        now = time.time()
        removed = 0
        for folder in (config.UPLOAD_DIR, config.OUTPUT_DIR):
            for path in folder.iterdir():
                try:
                    if path.name == ".gitkeep" or not path.is_file():
                        continue
                    if now - path.stat().st_mtime > max_age:
                        path.unlink()
                        removed += 1
                except OSError:
                    continue
        if removed:
            app.logger.info("Cleanup thread removed %d old file(s)", removed)


def create_app(testing: bool = False) -> Flask:
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(config)
    app.config["TESTING"] = testing

    config.ensure_dirs()
    _configure_logging()

    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_VIDEO_MB * 1024 * 1024

    _register_error_handlers(app)

    app.register_blueprint(core_routes.api, url_prefix="/api")
    app.register_blueprint(detection_routes.api, url_prefix="/api")
    app.register_blueprint(tracking_routes.api, url_prefix="/api")
    app.register_blueprint(lane_routes.api, url_prefix="/api")
    app.register_blueprint(depth_routes.api, url_prefix="/api")
    app.register_blueprint(simulation_routes.api, url_prefix="/api")
    app.register_blueprint(chat_routes.api, url_prefix="/api")
    app.register_blueprint(auth_routes.api, url_prefix="/api")

    def _api_info():
        return jsonify(
            {
                "success": True,
                "data": {
                    "service": "AI-Based Autonomous Driving System API",
                    "version": config.API_VERSION,
                    "endpoints": sorted(rule.rule for rule in app.url_map.iter_rules() if rule.rule.startswith("/api")),
                },
            }
        )

    @app.get("/api")
    def api_index():
        return _api_info()

    @app.get("/")
    def index():
        if config.FRONTEND_DIST.exists() and not testing:
            return send_from_directory(config.FRONTEND_DIST, "index.html")
        return _api_info()

    # --- load the trained model exactly once at startup ----------------------
    service = model_service.get_model_service()
    if not testing:
        started = time.perf_counter()
        service.load(config.MODEL_PATH)
        app.logger.info(
            "Model service status after startup: %s (%.0f ms)",
            service.status,
            (time.perf_counter() - started) * 1000,
        )
        cleanup_thread = threading.Thread(target=_cleanup_loop, args=(app,), daemon=True, name="temp-cleanup")
        cleanup_thread.start()

    # --- serve the built React SPA (production single-server mode) ----------
    if config.FRONTEND_DIST.exists() and not testing:
        static_dir = config.FRONTEND_DIST

        @app.get("/assets/<path:filename>")
        def spa_assets(filename):
            return send_from_directory(static_dir / "assets", filename)

        @app.get("/<path:subpath>")
        def spa_catch_all(subpath):
            """Return index.html for any non-API route (React Router handles it)."""
            # Don't intercept API or output file routes
            if subpath.startswith(("api/", "outputs/")):
                return jsonify({"success": False, "error": {"code": "NOT_FOUND", "message": "The requested resource does not exist."}}), 404
            candidate = static_dir / subpath
            if candidate.is_file():
                return send_from_directory(static_dir, subpath)
            return send_from_directory(static_dir, "index.html")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG, threaded=True)
