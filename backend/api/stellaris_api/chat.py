"""Project-scoped research chat, durable assistant messages, and chat generations."""

import json

from flask import Blueprint, current_app, g

from . import idempotency, runs
from .db import transaction
from .errors import ApiError
from .events import record_event
from .http import dumps, idempotency_key, json_body, json_response, new_id, now_ts, project_page
from .projects import load_visible, load_writable
from .refs import require_artifacts
from .validation import Validator

bp = Blueprint("chat", __name__, url_prefix="/api/v1/projects")
MAX_MESSAGE_CHARS = 50_000


def _message(project_id, role, text, *, attachments=(), run_id=None, status="complete", generation=0):
    ts = now_ts()
    return {"id": new_id("msg"), "project_id": project_id, "role": role,
            "content_markdown": text, "attachment_ids": list(attachments), "claim_ids": [],
            "run_id": run_id, "status": status, "last_chunk_index": None,
            "chat_generation": generation, "created_at": ts, "updated_at": ts}


def _save_message(conn, message, event="message.created"):
    conn.execute("INSERT INTO messages (id, project_id, role, created_at, doc, chat_generation) VALUES (?, ?, ?, ?, ?, ?)",
                 (message["id"], message["project_id"], message["role"], message["created_at"], dumps(message), message["chat_generation"]))
    record_event(conn, message["project_id"], event, {"message": message}, run_id=message["run_id"])


def _generation(conn, project_id):
    row = conn.execute("SELECT generation FROM chat_state WHERE project_id = ?", (project_id,)).fetchone()
    return int(row[0]) if row else 0


def _snapshot(conn, project_id, *, context_artifact_ids, attachments):
    artifacts = require_artifacts(conn, project_id, list(dict.fromkeys([*attachments, *context_artifact_ids])),
                                  "/context_artifact_ids")
    project = load_visible(conn, project_id)
    generation = _generation(conn, project_id)
    return {
        "version": 1, "chat_generation": generation,
        "project": {"id": project_id, "name": project["name"], "description": project["description"],
                    "research_question": project["research_question"]},
        "preceding_messages": [json.loads(r["doc"]) for r in conn.execute(
            "SELECT doc FROM messages WHERE project_id = ? AND chat_generation = ? ORDER BY created_at, id", (project_id, generation))],
        "sources": [json.loads(r["doc"]) for r in conn.execute(
            "SELECT doc FROM sources WHERE project_id = ? ORDER BY created_at, id", (project_id,))],
        "claims": [json.loads(r["doc"]) for r in conn.execute(
            "SELECT doc FROM claims WHERE project_id = ? ORDER BY created_at, id", (project_id,))],
        "experiments": [json.loads(r["doc"]) for r in conn.execute(
            "SELECT doc FROM experiments WHERE project_id = ? ORDER BY created_at, id", (project_id,))],
        "artifacts": list(artifacts.values()), "context_artifact_ids": list(context_artifact_ids),
    }


@bp.get("/<project_id>/messages")
def list_messages(project_id):
    load_visible(g.db, project_id)
    generation = _generation(g.db, project_id)
    rows, cursor = project_page(g.db, "messages", project_id, {}, fixed={"chat_generation": generation})
    return json_response({"items": [json.loads(row["doc"]) for row in rows], "next_cursor": cursor,
                          "generation": generation})


@bp.get("/<project_id>/messages/<message_id>")
def get_message(project_id, message_id):
    load_visible(g.db, project_id)
    row = g.db.execute("SELECT doc FROM messages WHERE id = ? AND project_id = ?", (message_id, project_id)).fetchone()
    if row is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Resource not found.")
    return json_response(json.loads(row["doc"]))


@bp.post("/<project_id>/messages")
def post_message(project_id):
    body = json_body()
    key = idempotency_key()
    v = Validator()
    v.unknown(body, {"content_markdown", "attachment_ids", "context_artifact_ids"})
    text = v.string(body, "content_markdown", min_len=1, max_len=MAX_MESSAGE_CHARS, strip=True)
    attachments = v.strings(body, "attachment_ids", required=False, max_items=50, min_len=1, max_len=100, unique=True)
    context = v.strings(body, "context_artifact_ids", required=False, max_items=50, min_len=1, max_len=100, unique=True)
    v.check()
    created = []

    def build(conn):
        load_writable(conn, project_id)
        active = conn.execute("SELECT 1 FROM runs WHERE project_id = ? AND kind = 'agent' "
                              "AND status IN ('queued', 'running', 'awaiting_approval', 'cancelling') LIMIT 1", (project_id,)).fetchone()
        if active:
            raise ApiError(409, "AGENT_RUN_IN_PROGRESS", "A research agent run is already active for this project.")
        generation = _generation(conn, project_id)
        snapshot = _snapshot(conn, project_id, context_artifact_ids=context, attachments=attachments)
        user = _message(project_id, "user", text, attachments=attachments, generation=generation)
        assistant = _message(project_id, "assistant", "", run_id=None, status="streaming", generation=generation)
        run_input = {"kind": "agent", "user_message_id": user["id"], "assistant_message_id": assistant["id"],
                     "attachment_ids": user["attachment_ids"], "context_artifact_ids": context,
                     "chat_generation": generation}
        snapshot["current_user_message"] = user
        run = runs.insert_run(conn, project_id, run_input, snapshot)
        assistant["run_id"] = run["id"]
        _save_message(conn, user)
        _save_message(conn, assistant)
        result = {"user_message": user, "assistant_message": assistant, "run": run}
        created.append(run["id"])
        return 202, result, {"Location": f"/api/v1/projects/{project_id}/runs/{run['id']}"}, run["id"]

    response = idempotency.run_command(g.db, key, body, build)
    if created:
        current_app.extensions["stellaris_runs"].enqueue(created[0])
    return response


@bp.post("/<project_id>/chat/clear")
def clear_chat(project_id):
    body = json_body()
    if body:
        raise ApiError(422, "VALIDATION_FAILED", "Request body must be an empty object.",
                       details={"field_errors": [{"path": f"/{key}", "message": "Unknown field."} for key in body]})
    key = idempotency_key()

    def build(conn):
        load_writable(conn, project_id)
        active = conn.execute("SELECT 1 FROM runs WHERE project_id = ? AND kind = 'agent' "
                              "AND status IN ('queued', 'running', 'awaiting_approval', 'cancelling') LIMIT 1", (project_id,)).fetchone()
        if active:
            raise ApiError(409, "CHAT_BUSY", "Chat cannot be cleared while an agent run is active.")
        current = _generation(conn, project_id)
        generation, ts = current + 1, now_ts()
        conn.execute("INSERT INTO chat_state (project_id, generation, cleared_at) VALUES (?, ?, ?) "
                     "ON CONFLICT(project_id) DO UPDATE SET generation = excluded.generation, cleared_at = excluded.cleared_at",
                     (project_id, generation, ts))
        payload = {"project_id": project_id, "generation": generation, "cleared_at": ts}
        record_event(conn, project_id, "chat.cleared", payload)
        return 200, payload, {}, project_id

    return idempotency.run_command(g.db, key, body, build)
