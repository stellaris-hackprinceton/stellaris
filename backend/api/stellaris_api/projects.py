"""Project routes: create, list, get, patch, workspace, events (Contracts.md sections 5-6, 8)."""

import logging
import time

from flask import Blueprint, Response, current_app, g, request

from . import db, events, idempotency
from .db import transaction
from .errors import ApiError, validation_error
from .events import record_event
from .http import (
    canonical_sha256, decode_cursor, dumps, encode_cursor, etag, idempotency_key,
    json_body, json_response, new_id, now_ts, page_limit, parse_if_match,
)
from .runtime import RuntimeUnavailable

log = logging.getLogger(__name__)

bp = Blueprint("projects", __name__, url_prefix="/api/v1/projects")

CREATE_FIELDS = {"name", "description", "research_question"}
PATCH_FIELDS = CREATE_FIELDS | {"status"}
STATUSES = ("active", "archived")
CREATE_SCOPE = "POST /api/v1/projects"
PROVISION_RETRY_AFTER_S = 5


# -- serialization ------------------------------------------------------------

def to_project(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "research_question": row["research_question"],
        "status": row["status"],
        "revision": row["revision"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def load_visible(conn, project_id: str):
    row = conn.execute(
        "SELECT * FROM projects WHERE id = ? AND runtime_state = 'ready'", (project_id,)
    ).fetchone()
    if row is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Resource not found.")
    return row


def load_writable(conn, project_id: str):
    """Visible project that accepts new writes (archived projects return 409)."""
    row = load_visible(conn, project_id)
    if row["status"] == "archived":
        raise ApiError(409, "PROJECT_ARCHIVED", "The project is archived. Restore it before making changes.")
    return row


# -- validation ---------------------------------------------------------------

def _validate(body: dict, allowed: set, *, creating: bool) -> dict:
    errors = [{"path": f"/{k}", "message": "Unknown field."} for k in sorted(body) if k not in allowed]
    values = {}

    if "name" in body or creating:
        name = body.get("name")
        if not isinstance(name, str):
            errors.append({"path": "/name", "message": "name is required and must be a string."})
        else:
            name = name.strip()
            if not 1 <= len(name) <= 120:
                errors.append({"path": "/name", "message": "name must contain 1-120 non-whitespace characters."})
            values["name"] = name

    if "description" in body:
        if not isinstance(body["description"], str):
            errors.append({"path": "/description", "message": "description must be a string."})
        values["description"] = body["description"]
    elif creating:
        values["description"] = ""

    if "research_question" in body:
        rq = body["research_question"]
        if rq is not None and not isinstance(rq, str):
            errors.append({"path": "/research_question", "message": "research_question must be a string or null."})
        values["research_question"] = rq
    elif creating:
        values["research_question"] = None

    if "status" in body and "status" in allowed:
        if body["status"] not in STATUSES:
            errors.append({"path": "/status", "message": "status must be 'active' or 'archived'."})
        values["status"] = body["status"]

    if errors:
        raise validation_error(errors)
    return values


# -- routes -------------------------------------------------------------------

@bp.post("")
def create_project():
    body = json_body()
    key = idempotency_key()
    values = _validate(body, CREATE_FIELDS, creating=True)
    body_hash = canonical_sha256(body)
    conn = g.db

    with transaction(conn):
        idempotency.purge_expired(conn)
        row, replay = idempotency.claim(conn, CREATE_SCOPE, key, body_hash)
        if replay is not None:
            return replay
        if row is not None:
            project_id = row["resource_id"]  # Retrying a previously failed provisioning.
            conn.execute(
                "UPDATE projects SET runtime_state = 'provisioning', runtime_error = NULL WHERE id = ?",
                (project_id,),
            )
        else:
            project_id = new_id("prj")
            ts = now_ts()
            conn.execute(
                "INSERT INTO projects (id, name, description, research_question, status, revision, "
                "created_at, updated_at, runtime_state) VALUES (?, ?, ?, ?, 'active', 1, ?, ?, 'provisioning')",
                (project_id, values["name"], values["description"], values["research_question"], ts, ts),
            )
            idempotency.begin(conn, CREATE_SCOPE, key, body_hash, project_id)

    runtime = current_app.extensions["stellaris_runtime"]
    try:
        runtime.ensure(project_id, create_volume=True, wait_healthy=True)
    except Exception as exc:  # Never leave a project looking provisioned after a failure.
        if isinstance(exc, RuntimeUnavailable):
            log.error("Provisioning failed for %s: %s", project_id, exc)
        else:
            log.exception("Unexpected provisioning failure for %s", project_id)
        with transaction(conn):
            conn.execute(
                "UPDATE projects SET runtime_state = 'failed', runtime_error = ? WHERE id = ?",
                (str(exc)[:1000], project_id),
            )
            idempotency.mark_failed(conn, CREATE_SCOPE, key)
        raise ApiError(
            503, "SERVICE_UNAVAILABLE",
            "The project workspace could not be provisioned. Retry with the same Idempotency-Key.",
            retryable=True, headers={"Retry-After": str(PROVISION_RETRY_AFTER_S)},
        )

    with transaction(conn):
        conn.execute(
            "UPDATE projects SET runtime_state = 'ready', runtime_error = NULL WHERE id = ?", (project_id,)
        )
        project = to_project(conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())
        record_event(conn, project_id, "project.updated", {"project": project})
        headers = {"Location": f"/api/v1/projects/{project_id}", "ETag": etag(project["revision"])}
        idempotency.complete(conn, CREATE_SCOPE, key, 201, dumps(project), headers)

    return json_response(project, 201, headers)


@bp.get("")
def list_projects():
    limit = page_limit()
    status = request.args.get("status")
    if status is not None and status not in STATUSES:
        raise ApiError(400, "INVALID_QUERY", "status must be 'active' or 'archived'.")

    after = None
    cursor = request.args.get("cursor")
    if cursor:
        state = decode_cursor(cursor)
        if state.get("v") != 1 or not isinstance(state.get("u"), str) or not isinstance(state.get("i"), str):
            raise ApiError(400, "INVALID_CURSOR", "cursor is invalid.")
        if status is not None and status != state.get("s"):
            raise ApiError(400, "INVALID_QUERY", "Query filters must match the filters used to create the cursor.")
        status = state.get("s")  # Cursors preserve their original filters.
        after = (state["u"], state["i"])

    sql = "SELECT * FROM projects WHERE runtime_state = 'ready'"
    params = []
    if status is not None:
        sql += " AND status = ?"
        params.append(status)
    if after is not None:
        sql += " AND (updated_at < ? OR (updated_at = ? AND id < ?))"
        params += [after[0], after[0], after[1]]
    sql += " ORDER BY updated_at DESC, id DESC LIMIT ?"
    params.append(limit + 1)

    rows = g.db.execute(sql, params).fetchall()
    items = [to_project(r) for r in rows[:limit]]
    next_cursor = None
    if len(rows) > limit:
        last = items[-1]
        next_cursor = encode_cursor({"v": 1, "u": last["updated_at"], "i": last["id"], "s": status})
    return json_response({"items": items, "next_cursor": next_cursor})


@bp.get("/<project_id>")
def get_project(project_id):
    project = to_project(load_visible(g.db, project_id))
    return json_response(project, 200, {"ETag": etag(project["revision"])})


@bp.patch("/<project_id>")
def patch_project(project_id):
    body = json_body()
    if not body:
        raise validation_error([{"path": "", "message": "At least one field is required."}])
    values = _validate(body, PATCH_FIELDS, creating=False)
    expected = parse_if_match()
    if expected is None:
        raise ApiError(428, "PRECONDITION_REQUIRED", "If-Match with the project's current ETag is required.")

    conn = g.db
    with transaction(conn):
        row = load_visible(conn, project_id)
        if row["revision"] != expected:
            raise ApiError(412, "REVISION_CONFLICT",
                           "The project changed since it was loaded. Reload and reconcile edits.",
                           details={"current_revision": row["revision"]})
        if row["status"] == "archived" and values.get("status") != "active":
            raise ApiError(409, "PROJECT_ARCHIVED",
                           "The project is archived. Restore it with status 'active' before editing.")

        current = to_project(row)
        changes = {k: v for k, v in values.items() if current[k] != v}
        if changes:
            changes["revision"] = row["revision"] + 1
            changes["updated_at"] = now_ts()
            assignments = ", ".join(f"{k} = ?" for k in changes)
            conn.execute(f"UPDATE projects SET {assignments} WHERE id = ?", [*changes.values(), project_id])
            current = to_project(conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())
            record_event(conn, project_id, "project.updated", {"project": current})

    return json_response(current, 200, {"ETag": etag(current["revision"])})


@bp.get("/<project_id>/workspace")
def get_workspace(project_id):
    conn = g.db
    with transaction(conn, immediate=False):  # One consistent read snapshot.
        project = to_project(load_visible(conn, project_id))
        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table} WHERE project_id = ?", (project_id,)).fetchone()[0]
            for table in ("sources", "experiments", "artifacts", "runs")
        }
        active = [r["id"] for r in conn.execute(
            "SELECT id FROM runs WHERE project_id = ? AND status IN ('queued', 'running', 'awaiting_approval', "
            "'cancelling') ORDER BY created_at, id", (project_id,))]
        report = conn.execute("SELECT id FROM artifacts WHERE project_id = ? AND kind = 'report' "
                              "ORDER BY created_at DESC, id DESC LIMIT 1", (project_id,)).fetchone()
        latest = events.latest_sequence(conn, project_id)
    return json_response(
        {
            "project": project,
            "counts": counts,
            "active_run_ids": active,
            "latest_report_artifact_id": report["id"] if report else None,
            "event_cursor": events.event_cursor(project_id, latest),
        }
    )


SSE_POLL_S = 0.5
SSE_HEARTBEAT_S = 15
SSE_BATCH = 200


@bp.get("/<project_id>/events")
def stream_events(project_id):
    """Ordered replay of persisted events strictly after a cursor, then live polling.

    Last-Event-ID (sent by EventSource on reconnect) takes precedence over ?after=.
    With neither, the stream starts at the latest event (live only).
    """
    config = current_app.config["STELLARIS"]
    conn = g.db
    load_visible(conn, project_id)
    raw = request.headers.get("Last-Event-ID", "").strip() or request.args.get("after")
    with transaction(conn):
        events.purge_expired(conn, project_id, config.event_retention_s)
        oldest, newest = conn.execute(
            "SELECT MIN(sequence), COALESCE(MAX(sequence), 0) FROM events WHERE project_id = ?", (project_id,)
        ).fetchone()
    if raw is None:
        after = newest
    else:
        after = events.parse_event_cursor(project_id, raw)
        if after is None or after > newest:
            raise ApiError(400, "INVALID_EVENT_CURSOR", "Event cursor is invalid for this project.")
        if oldest is not None and after < oldest - 1:
            raise ApiError(410, "EVENT_CURSOR_EXPIRED",
                           "Event cursor is older than the retained history. Reload the workspace.")

    db_path = config.db_path

    def generate():
        # Runs after the request context ends, so it owns a separate connection.
        stream_conn = db.connect(db_path)
        last_sequence, last_write = after, time.monotonic()
        try:
            yield "retry: 3000\n\n"
            while True:
                rows = stream_conn.execute(
                    "SELECT * FROM events WHERE project_id = ? AND sequence > ? ORDER BY sequence LIMIT ?",
                    (project_id, last_sequence, SSE_BATCH),
                ).fetchall()
                for row in rows:
                    yield events.to_sse(project_id, row)
                    last_sequence = row["sequence"]
                if rows:
                    last_write = time.monotonic()
                    continue
                if time.monotonic() - last_write >= SSE_HEARTBEAT_S:
                    yield ": heartbeat\n\n"
                    last_write = time.monotonic()
                time.sleep(SSE_POLL_S)
        finally:
            stream_conn.close()

    response = Response(generate(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-store, no-transform"
    response.headers["X-Accel-Buffering"] = "no"  # Ask reverse proxies not to buffer.
    return response
