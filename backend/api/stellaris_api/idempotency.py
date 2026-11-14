"""Idempotency-Key bookkeeping for JSON POST commands (docs/frontend-backend-contract.md section 3).

States:
  in_progress  a request holds the key; others get 409 COMMAND_IN_PROGRESS until the lease ends
  failed       the command failed retryably (e.g. Docker unavailable); the same key may retry
  complete     the stored status/body/headers are replayed for the same key and body

Development mode has no users, so keys are scoped to "METHOD route".
All functions expect to be called inside db.transaction().
"""

import json
from datetime import datetime, timedelta, timezone

from flask import Response, request

from .db import transaction
from .errors import ApiError
from .http import TIMESTAMP_FORMAT, canonical_sha256, dumps, json_response, now_ts, parse_ts

LEASE_SECONDS = 120
RETENTION_SECONDS = 24 * 3600
RETRY_AFTER_SECONDS = 2


def purge_expired(conn) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=RETENTION_SECONDS)).strftime(TIMESTAMP_FORMAT)
    conn.execute("DELETE FROM idempotency_keys WHERE created_at < ?", (cutoff,))


def claim(conn, scope: str, key: str, body_sha256: str):
    """Look up a key. Returns (row_or_None, replay_response_or_None).

    Raises ApiError for a body mismatch or a command still in progress.
    When a row is returned without a replay, its lease has been (re)taken by this request.
    """
    row = conn.execute(
        "SELECT * FROM idempotency_keys WHERE scope = ? AND key = ?", (scope, key)
    ).fetchone()
    if row is None:
        return None, None
    if row["body_sha256"] != body_sha256:
        raise ApiError(409, "IDEMPOTENCY_CONFLICT",
                       "This Idempotency-Key was already used with a different request body.")
    if row["state"] == "complete":
        return row, replay(row)
    if row["state"] == "in_progress":
        age = datetime.now(timezone.utc) - parse_ts(row["updated_at"])
        if age.total_seconds() < LEASE_SECONDS:
            raise ApiError(409, "COMMAND_IN_PROGRESS",
                           "The original request with this Idempotency-Key is still being processed.",
                           retryable=True, headers={"Retry-After": str(RETRY_AFTER_SECONDS)})
    conn.execute(
        "UPDATE idempotency_keys SET state = 'in_progress', updated_at = ? WHERE scope = ? AND key = ?",
        (now_ts(), scope, key),
    )
    return row, None


def begin(conn, scope: str, key: str, body_sha256: str, resource_id) -> None:
    ts = now_ts()
    conn.execute(
        "INSERT INTO idempotency_keys (scope, key, body_sha256, state, resource_id, created_at, updated_at) "
        "VALUES (?, ?, ?, 'in_progress', ?, ?, ?)",
        (scope, key, body_sha256, resource_id, ts, ts),
    )


def mark_failed(conn, scope: str, key: str) -> None:
    conn.execute(
        "UPDATE idempotency_keys SET state = 'failed', updated_at = ? WHERE scope = ? AND key = ?",
        (now_ts(), scope, key),
    )


def complete(conn, scope: str, key: str, status: int, body: str, headers: dict) -> None:
    conn.execute(
        "UPDATE idempotency_keys SET state = 'complete', response_status = ?, response_body = ?, "
        "response_headers = ?, updated_at = ? WHERE scope = ? AND key = ?",
        (status, body, json.dumps(headers), now_ts(), scope, key),
    )


def replay(row) -> Response:
    response = Response(row["response_body"], status=row["response_status"], mimetype="application/json")
    for name, value in json.loads(row["response_headers"] or "{}").items():
        response.headers[name] = value
    response.headers["Idempotent-Replayed"] = "true"
    return response


def request_scope() -> str:
    return f"{request.method} {request.path}"


def run_command(conn, key: str, body: dict, build):
    """Run a single-transaction JSON POST command with idempotent replay.

    build(conn) -> (status, payload, headers, resource_id) runs inside the same transaction
    as the idempotency record, so the resource, its events, and the stored response commit
    together. If build raises, nothing (including the key) is stored.
    """
    scope, body_hash = request_scope(), canonical_sha256(body)
    with transaction(conn):
        purge_expired(conn)
        row, replayed = claim(conn, scope, key, body_hash)
        if replayed is not None:
            return replayed
        status, payload, headers, resource_id = build(conn)
        if row is None:
            begin(conn, scope, key, body_hash, resource_id)
        complete(conn, scope, key, status, dumps(payload), headers)
    return json_response(payload, status, headers)


def recover_after_restart(conn) -> int:
    """No request survives a process restart; release its keys for retry."""
    cursor = conn.execute(
        "UPDATE idempotency_keys SET state = 'failed', updated_at = ? WHERE state = 'in_progress'",
        (now_ts(),),
    )
    return cursor.rowcount
