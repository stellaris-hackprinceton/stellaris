"""Approvals (Contracts.md section 7; `remote_compute` added in 1.1, ADR-0001).

A handler that needs explicit authorization calls request() inside its run: the approval and
the run's move to `awaiting_approval` commit together, and the handler returns suspended
(no executor slot is held while waiting). An approve decision moves the run back to
`running` and re-enqueues it; the handler then finds the approved approval and proceeds with
exactly its action snapshot. Rejection or expiry cancels the run with a result warning.
Approval binds to the snapshot hash and a single execution.
"""

import hashlib
import json
from datetime import timedelta

from flask import Blueprint, current_app, g

from . import idempotency, runs
from .db import transaction
from .errors import ApiError, validation_error
from .events import record_event
from .http import (TIMESTAMP_FORMAT, dumps, idempotency_key, json_body, json_response, new_id, now_ts, parse_ts,
                   project_page)
from .projects import load_visible

bp = Blueprint("approvals", __name__, url_prefix="/api/v1/projects")

def action_sha256(snapshot: dict) -> str:
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _save(conn, approval, event_type):
    conn.execute("UPDATE approvals SET status = ?, doc = ? WHERE id = ?",
                 (approval["status"], dumps(approval), approval["id"]))
    record_event(conn, approval["project_id"], event_type, {"approval": approval}, run_id=approval["run_id"])


def for_run(conn, run_id: str):
    return [json.loads(r["doc"]) for r in conn.execute(
        "SELECT doc FROM approvals WHERE run_id = ? ORDER BY created_at, id", (run_id,))]


def approved_action(conn, run_id: str, action_type: str):
    """The approved, not yet consumed action snapshot for this run, or None."""
    for approval in reversed(for_run(conn, run_id)):
        if approval["action_type"] == action_type and approval["status"] == "approved":
            return approval["action_snapshot"]
    return None


def request(conn, ttl_s: int, *, project_id, run_id, action_type, summary, action_snapshot, estimated_cost=None):
    """Persist a pending approval and move the run to awaiting_approval (caller's transaction)."""
    created = parse_ts(now_ts())
    approval = {
        "id": new_id("apr"), "project_id": project_id, "run_id": run_id, "action_type": action_type,
        "summary": summary, "action_snapshot": action_snapshot, "action_sha256": action_sha256(action_snapshot),
        "estimated_cost": estimated_cost, "status": "pending", "created_at": created.strftime(TIMESTAMP_FORMAT),
        "expires_at": (created + timedelta(seconds=ttl_s)).strftime(TIMESTAMP_FORMAT), "decided_at": None,
    }
    conn.execute("INSERT INTO approvals (id, project_id, run_id, status, created_at, doc) VALUES (?, ?, ?, ?, ?, ?)",
                 (approval["id"], project_id, run_id, "pending", approval["created_at"], dumps(approval)))
    record_event(conn, project_id, "approval.required", {"approval": approval}, run_id=run_id)
    runs.save_run(conn, run_id, status="awaiting_approval", phase="awaiting_approval",
                  progress={"fraction": None, "message": summary})
    return approval


def expire_for_run(conn, run_id: str) -> None:
    """Cancellation or terminal failure expires the run's outstanding approvals."""
    for approval in for_run(conn, run_id):
        if approval["status"] == "pending":
            approval.update(status="expired", decided_at=now_ts())
            _save(conn, approval, "approval.updated")


def _cancel_run(conn, run_id, code, message):
    runs.add_warnings(conn, run_id, [{"code": code, "message": message}])
    run = json.loads(conn.execute("SELECT doc FROM runs WHERE id = ?", (run_id,)).fetchone()["doc"])
    if run["status"] == "awaiting_approval":
        runs.save_run(conn, run_id, status="cancelled", finished_at=now_ts(), phase="cancelled",
                      result_summary=message, progress={"fraction": None, "message": message})


def sweep_expired(conn) -> int:
    """Expire pending approvals past expires_at and cancel their runs. Returns the count."""
    now = now_ts()
    expired = 0
    with transaction(conn):
        for row in conn.execute("SELECT doc FROM approvals WHERE status = 'pending'").fetchall():
            approval = json.loads(row["doc"])
            if approval["expires_at"] <= now:
                approval.update(status="expired", decided_at=now)
                _save(conn, approval, "approval.updated")
                _cancel_run(conn, approval["run_id"], "APPROVAL_EXPIRED",
                            "The approval expired before a decision; the run was cancelled.")
                expired += 1
    return expired


@bp.get("/<project_id>/runs/<run_id>/approvals")
def list_approvals(project_id, run_id):
    load_visible(g.db, project_id)
    runs.load_run_row(g.db, project_id, run_id)
    rows, next_cursor = project_page(g.db, "approvals", project_id, {}, fixed={"run_id": run_id})
    return json_response({"items": [json.loads(r["doc"]) for r in rows], "next_cursor": next_cursor})


@bp.post("/<project_id>/approvals/<approval_id>/decision")
def decide(project_id, approval_id):
    body = json_body()
    key = idempotency_key()
    if set(body) != {"decision", "action_sha256"} or body.get("decision") not in ("approve", "reject") \
            or not isinstance(body.get("action_sha256"), str):
        raise validation_error([{"path": "", "message": "Body must be {decision: approve|reject, action_sha256}."}])
    resume = []

    def build(conn):
        load_visible(conn, project_id)
        row = conn.execute("SELECT doc FROM approvals WHERE id = ? AND project_id = ?",
                           (approval_id, project_id)).fetchone()
        if row is None:
            raise ApiError(404, "RESOURCE_NOT_FOUND", "Resource not found.")
        approval = json.loads(row["doc"])
        wanted = "approved" if body["decision"] == "approve" else "rejected"
        if body["action_sha256"] != approval["action_sha256"]:
            raise ApiError(409, "APPROVAL_CHANGED", "The action changed since it was shown; review it again.")
        if approval["status"] == wanted:
            return 200, approval, {}, approval_id
        if approval["status"] != "pending":
            raise ApiError(409, "APPROVAL_ALREADY_DECIDED", f"This approval is already {approval['status']}.")
        if approval["expires_at"] <= now_ts():
            approval.update(status="expired", decided_at=now_ts())
            _save(conn, approval, "approval.updated")
            _cancel_run(conn, approval["run_id"], "APPROVAL_EXPIRED",
                        "The approval expired before a decision; the run was cancelled.")
            return 200, approval, {}, approval_id
        run = json.loads(conn.execute("SELECT doc FROM runs WHERE id = ?", (approval["run_id"],)).fetchone()["doc"])
        if run["status"] != "awaiting_approval":
            raise ApiError(409, "APPROVAL_ALREADY_DECIDED", "The run is no longer waiting for this approval.")
        approval.update(status=wanted, decided_at=now_ts())
        _save(conn, approval, "approval.updated")
        if wanted == "approved":
            runs.save_run(conn, approval["run_id"], status="running", phase="approved",
                          progress={"fraction": None, "message": "Approved; preparing remote execution."})
            resume.append(approval["run_id"])
        else:
            _cancel_run(conn, approval["run_id"], "APPROVAL_REJECTED", "The approval was rejected; the run was cancelled.")
        return 200, approval, {}, approval_id

    response = idempotency.run_command(g.db, key, body, build)
    for run_id in resume:
        current_app.extensions["stellaris_runs"].resume(run_id)
    return response
