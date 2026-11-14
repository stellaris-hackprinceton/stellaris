"""Flask application factory, system routes, request guards, and restart reconciliation."""

import logging
import threading
import uuid

from flask import Flask, g, request

from . import artifacts, db, experiments, idempotency, research
from .config import load_config
from .errors import ApiError, register_error_handlers
from .http import json_response
from .media import UPLOAD_MIME_TYPES
from .projects import bp as projects_bp
from .runtime import ProjectRuntime, RuntimeUnavailable

log = logging.getLogger(__name__)

CONTRACT_VERSION = "1.0.0-draft"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def create_app(config=None) -> Flask:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = config or load_config()
    db.init_db(config.db_path)

    app = Flask(__name__)
    # Limits JSON bodies. Upload content PUTs read the WSGI input directly and enforce the
    # upload's declared size themselves.
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
    app.config["STELLARIS"] = config
    runtime = ProjectRuntime(config)
    app.extensions["stellaris_runtime"] = runtime

    register_error_handlers(app)
    for blueprint in (projects_bp, research.bp, experiments.bp, artifacts.bp):
        app.register_blueprint(blueprint)
    _register_guards(app, config)
    _register_system_routes(app, config, runtime)

    _recover_database(config)
    artifacts.cleanup_uploads(config)
    threading.Thread(target=_reconcile_containers, args=(config, runtime), daemon=True,
                     name="stellaris-reconcile").start()
    return app


def _host_without_port(host: str) -> str:
    if host.startswith("["):
        return host[: host.find("]") + 1]
    return host.split(":", 1)[0]


def _register_guards(app, config):
    @app.before_request
    def _before():
        g.request_id = f"req_{uuid.uuid4().hex}"
        # No authentication in development mode, so guard against DNS rebinding and
        # cross-site requests from other browser origins.
        if _host_without_port(request.host) not in config.allowed_hosts:
            raise ApiError(403, "ACTION_FORBIDDEN", "Host is not allowed.")
        origin = request.headers.get("Origin")
        if request.method in UNSAFE_METHODS and origin is not None and origin not in config.allowed_origins:
            raise ApiError(403, "CSRF_FAILED", "Request origin is not allowed.")
        g.db = db.connect(config.db_path)

    @app.after_request
    def _after(response):
        response.headers["X-Request-ID"] = g.get("request_id", "")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.teardown_request
    def _teardown(_exc):
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()


def _register_system_routes(app, config, runtime):
    @app.get("/api/v1/health")
    def health():
        database_ok = True
        try:
            g.db.execute("SELECT 1").fetchone()
        except Exception:  # pragma: no cover - reported, not raised
            database_ok = False
        docker_ok = runtime.ping()
        ok = database_ok and docker_ok
        body = {
            "status": "ok" if ok else "degraded",
            "database": "ok" if database_ok else "unavailable",
            "docker": "ok" if docker_ok else "unavailable",
        }
        return json_response(body, 200 if ok else 503)

    @app.get("/api/v1/session")
    def session():
        # Development compatibility response: authentication is intentionally omitted.
        return json_response(
            {
                "user": {"id": "usr_local_development", "display_name": "Local development user"},
                "csrf_token": "",
                "contract_version": CONTRACT_VERSION,
                "auth_mode": "development_none",
            }
        )

    @app.get("/api/v1/capabilities")
    def capabilities():
        # Report only what is actually implemented. Zero limits mean "not available".
        # Uploads and events are implemented; agent design, analysis, and reports are not yet.
        return json_response(
            {
                "api_version": "v1",
                "features": {
                    "literature_search": False,
                    "experiment_design": False,
                    "video_analysis": False,
                    "image_analysis": False,
                    "audio_analysis": False,
                    "markdown_reports": False,
                    "remote_compute": False,
                    "collaboration": False,
                },
                "uploads": {
                    "accepted_mime_types": UPLOAD_MIME_TYPES,
                    "max_file_bytes": config.max_file_bytes,
                    "max_video_duration_ms": config.max_video_duration_ms,
                    "max_project_bytes": config.max_project_bytes,
                },
                "execution": {
                    "allowed_backends": [],
                    "max_wall_time_s": 0,
                    "max_memory_mb": 0,
                    "max_cpu_cores": 0,
                    "network_access": False,
                },
                "literature_providers": [],
                "event_retention_seconds": config.event_retention_s,
                "max_log_chunk_bytes": 0,
            }
        )


def _recover_database(config) -> None:
    """Runs before serving. With one Gunicorn worker nothing else is in flight."""
    conn = db.connect(config.db_path)
    try:
        with db.transaction(conn):
            released = idempotency.recover_after_restart(conn)
            interrupted = conn.execute(
                "UPDATE projects SET runtime_state = 'failed', "
                "runtime_error = 'Provisioning interrupted by backend restart.' "
                "WHERE runtime_state = 'provisioning'"
            ).rowcount
        if released or interrupted:
            log.warning("Recovered %d idempotency keys and %d interrupted provisionings", released, interrupted)
    finally:
        conn.close()


def _reconcile_containers(config, runtime) -> None:
    """Ensure every provisioned project (active or archived) has a running container.

    Missing containers are recreated against the existing workspace volume. A missing
    volume is reported and never replaced with an empty one.
    """
    conn = db.connect(config.db_path)
    try:
        project_ids = [r["id"] for r in conn.execute("SELECT id FROM projects WHERE runtime_state = 'ready'")]
    finally:
        conn.close()
    for project_id in project_ids:
        try:
            runtime.ensure(project_id, create_volume=False, wait_healthy=False)
        except RuntimeUnavailable as exc:
            log.error("Reconciliation failed for %s: %s", project_id, exc)
        except Exception:
            log.exception("Unexpected reconciliation failure for %s", project_id)
    log.info("Reconciled %d project containers", len(project_ids))
