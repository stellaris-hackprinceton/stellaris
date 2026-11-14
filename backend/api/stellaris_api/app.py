"""Flask application factory, system routes, request guards, and restart reconciliation."""

import atexit
import logging
import threading
import uuid

from flask import Flask, g, request

from . import agent_management, agent_runs, analysis, approvals, artifacts, catalog, chat, db, experiments, file_collections, files, hpc, idempotency, papers, reports, research, runs, worker
from .config import load_config
from .errors import ApiError, register_error_handlers
from .executor import RunManager
from .http import json_response
from .media import UPLOAD_MIME_TYPES
from .projects import bp as projects_bp
from .runtime import ProjectRuntime, RuntimeUnavailable
from .terminals import TerminalManager, create_blueprint as terminal_blueprint, init_schema as init_terminal_schema

log = logging.getLogger(__name__)

CONTRACT_VERSION = "1.0.0-draft"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def create_app(config=None) -> Flask:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = config or load_config()
    db.init_db(config.db_path)
    terminal_conn = db.connect(config.db_path)
    try:
        init_terminal_schema(terminal_conn)
        agent_management.init_schema(terminal_conn)
    finally:
        terminal_conn.close()

    app = Flask(__name__)
    # Limits JSON bodies. Upload content PUTs read the WSGI input directly and enforce the
    # upload's declared size themselves.
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
    app.config["STELLARIS"] = config
    runtime = ProjectRuntime(config)
    app.extensions["stellaris_runtime"] = runtime
    terminal_manager = TerminalManager(config, runtime)
    terminal_manager.start()
    app.extensions["stellaris_terminals"] = terminal_manager
    atexit.register(terminal_manager.close_all)
    # Shared run executor; agent coordination stays in the project runtime.
    manager = RunManager(config, runtime)
    manager.register_handler("agent", agent_runs.handle_agent_run)
    manager.register_handler("analysis", analysis.handle_analysis)
    manager.register_handler("report", reports.handle_report)
    manager.register_handler("paper_ingest", papers.handle_paper_ingest)
    manager.cluster = hpc.SlurmCluster(config, runtime) if config.slurm_host else None
    if manager.cluster is not None:
        try:
            manager.cluster.ensure_key()
        except OSError:
            log.exception("Could not prepare Slurm transport; remote execution stays unavailable")
    app.extensions["stellaris_runs"] = manager

    register_error_handlers(app)
    for blueprint in (projects_bp, research.bp, experiments.bp, artifacts.bp, runs.bp, chat.bp, files.bp, file_collections.bp, approvals.bp, agent_management.bp):
        app.register_blueprint(blueprint)
    app.register_blueprint(terminal_blueprint(terminal_manager))
    _register_guards(app, config)
    _register_system_routes(app, config, runtime, manager)

    queued, lost_agents = _recover_database(config)
    agent_runs.cleanup_lost_agents(runtime, lost_agents)
    artifacts.cleanup_uploads(config)
    analysis.cleanup_run_tmp(config)
    manager.start()
    for run_id, mode in queued:
        if mode == "resume":
            manager.resume(run_id)
        else:
            manager.enqueue(run_id, remote=mode)
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


def _register_system_routes(app, config, runtime, manager):
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
        # Report only what is actually implemented and available. Zero limits mean "not
        # available". Video analysis (bouncing_ball_v1) and isolated Python execution need the
        # worker image; Markdown reports run in the API (they still need evidence runs).
        workers = manager.worker_available()
        available_runtimes = worker.available_runtimes(runtime, config) if workers else []
        remote = manager.cluster.capabilities() if workers and manager.cluster is not None else None
        provider, _model, _runtime_env, agent_error, _message = agent_runs.selected_model_config()
        agent_configured = agent_error is None
        return json_response(
            {
                "api_version": "v1",
                "model_provider": provider,
                "model_configured": agent_configured,
                "features": {
                    "literature_search": agent_configured,
                    "experiment_design": agent_configured,
                    "research_chat": agent_configured,
                    "video_analysis": workers,
                    "image_analysis": False,
                    "audio_analysis": False,
                    "markdown_reports": True,
                    "remote_compute": remote is not None,
                    "full_text_papers": workers,
                    "collaboration": False,
                    # Additive file catalog, revisioned notes, tags, collections and links.
                    "workspace_files": True,
                    # Catalog schema 2 (contract section 16): collection presentation, artifact-kind
                    # file selection and saved filters, and exact origin lookup. Complete support only.
                    "workspace_views": True,
                    "agent_controls": True,
                    "agent_code_execution": bool(available_runtimes),
                    "terminal": app.extensions["stellaris_terminals"].available(),
                },
                "uploads": {
                    "accepted_mime_types": UPLOAD_MIME_TYPES,
                    "max_file_bytes": config.max_file_bytes,
                    "max_video_duration_ms": config.max_video_duration_ms,
                    "max_project_bytes": config.max_project_bytes,
                },
                "execution": {
                    "runtimes": [{"id": value, "label": {"python": "Python", "javascript": "JavaScript", "shell": "Shell"}.get(value, value)} for value in available_runtimes],
                    "allowed_backends": (["isolated_python"] + (["slurm"] if remote else [])) if workers else [],
                    # Additive, informational descriptors; they do not change validation.
                    "analysis_pipelines": (
                        [
                            {
                                "id": "bouncing_ball_v1",
                                "description": (
                                    "Tracks one bouncing ball; measures bounce heights and energy ratios. "
                                    "Object hint does not select a detector."
                                ),
                                "requires_code_artifact": False,
                            },
                            {
                                "id": "python_analysis_v1",
                                "description": (
                                    "Runs a supplied Python code artifact in an isolated worker; "
                                    "legacy Python script execution."
                                ),
                                "requires_code_artifact": True,
                            },
                        ] + ([{"id": "script_analysis_v1", "description": "Runs saved agent-generated or supplied code in an installed worker runtime.", "requires_code_artifact": True}] if available_runtimes else [])
                        if workers
                        else []
                    ),
                    "max_wall_time_s": config.worker_wall_time_s if workers else 0,
                    "max_memory_mb": config.worker_memory_mb if workers else 0,
                    "max_cpu_cores": config.worker_cpus if workers else 0,
                    "network_access": False,
                },
                "terminal": {
                    "network_access": False, "max_output_bytes": 2 * 1024 * 1024,
                    "max_input_bytes": 16 * 1024, "max_active_per_project": 1,
                    "max_duration_s": app.extensions["stellaris_terminals"].settings.duration_s,
                },
                "remote_compute": remote,
                "literature_providers": ["arxiv"] if agent_configured else [],
                "event_retention_seconds": config.event_retention_s,
                "max_log_chunk_bytes": config.max_log_chunk_bytes,
            }
        )


def _recover_database(config):
    """Runs before serving. With one Gunicorn worker nothing else is in flight.

    Returns the IDs of queued runs to re-enqueue."""
    conn = db.connect(config.db_path)
    try:
        with db.transaction(conn):
            released = idempotency.recover_after_restart(conn)
            interrupted = conn.execute(
                "UPDATE projects SET runtime_state = 'failed', "
                "runtime_error = 'Provisioning interrupted by backend restart.' "
                "WHERE runtime_state = 'provisioning'"
            ).rowcount
            queued, lost = runs.recover_after_restart(conn)
        if released or interrupted:
            log.warning("Recovered %d idempotency keys and %d interrupted provisionings", released, interrupted)
        if lost:
            log.warning("Marked %d interrupted runs as WORKER_LOST/cancelled: %s", len(lost), ", ".join(lost))
        lost_agents = []
        for run_id in lost:
            row = conn.execute("SELECT project_id,kind FROM runs WHERE id = ?", (run_id,)).fetchone()
            if row["kind"] == "agent":
                lost_agents.append((row["project_id"], run_id))
        return queued, lost_agents
    finally:
        conn.close()


def _reconcile_containers(config, runtime) -> None:
    """Ensure active provisioned projects have a running container.

    Missing containers are recreated against the existing workspace volume. A missing
    volume is reported and never replaced with an empty one.
    """
    try:
        worker.cleanup_orphans(runtime, lambda: db.connect(config.db_path))
    except Exception:
        log.exception("Worker orphan cleanup failed")
    try:  # Deliver catalog events committed before a restart; never creates catalogs.
        catalog.relay_all(config)
    except Exception:
        log.exception("Catalog event relay at startup failed")
    conn = db.connect(config.db_path)
    try:
        # Archived test runtimes explicitly removed by the user must not be resurrected.
        # Keep their volumes and records; this does not stop existing archived containers.
        project_ids = [r["id"] for r in conn.execute("SELECT id FROM projects WHERE runtime_state = 'ready' AND status = 'active'")]
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
