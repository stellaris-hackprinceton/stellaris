"""Persisted project events and opaque, project-bound event cursors (Contracts.md section 8).

Events are written with record_event() inside the same transaction as the resource change
they describe, so an event never points at uncommitted state. Writers use BEGIN IMMEDIATE,
which serializes sequence allocation and commit order per database.
"""

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone

from .http import TIMESTAMP_FORMAT, dumps, now_ts

_CURSOR = re.compile(r"^evt_(\d{6,12})_([0-9a-f]{12})$")


def _tag(project_id: str, sequence: int) -> str:
    # Binds a cursor to its project. Not a secret: project IDs are not an authorization boundary.
    return hashlib.sha256(f"stellaris-event:{project_id}:{sequence}".encode()).hexdigest()[:12]


def event_cursor(project_id: str, sequence: int) -> str:
    return f"evt_{sequence:06d}_{_tag(project_id, sequence)}"


def parse_event_cursor(project_id: str, cursor: str):
    """Return the sequence for a cursor issued for this project, or None if invalid."""
    match = _CURSOR.match(cursor or "")
    if not match:
        return None
    sequence = int(match.group(1))
    return sequence if match.group(2) == _tag(project_id, sequence) else None


def record_event(conn, project_id: str, event_type: str, payload: dict, run_id=None) -> int:
    """Persist one event in the caller's transaction and return its sequence."""
    sequence = conn.execute(
        "SELECT COALESCE(MAX(sequence), 0) + 1 FROM events WHERE project_id = ?", (project_id,)
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO events (project_id, sequence, type, run_id, payload, occurred_at) VALUES (?, ?, ?, ?, ?, ?)",
        (project_id, sequence, event_type, run_id, dumps(payload), now_ts()),
    )
    return sequence


def latest_sequence(conn, project_id: str) -> int:
    return conn.execute(
        "SELECT COALESCE(MAX(sequence), 0) FROM events WHERE project_id = ?", (project_id,)
    ).fetchone()[0]


def purge_expired(conn, project_id: str, retention_s: int) -> None:
    """Drop events older than retention, always keeping the newest so sequences never restart."""
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=retention_s)).strftime(TIMESTAMP_FORMAT)
    conn.execute(
        "DELETE FROM events WHERE project_id = ? AND occurred_at < ? "
        "AND sequence < (SELECT MAX(sequence) FROM events WHERE project_id = ?)",
        (project_id, cutoff, project_id),
    )


def to_sse(project_id: str, row) -> str:
    cursor = event_cursor(project_id, row["sequence"])
    data = dumps({
        "cursor": cursor, "project_id": project_id, "type": row["type"],
        "occurred_at": row["occurred_at"], "run_id": row["run_id"], "payload": json.loads(row["payload"]),
    })  # Compact JSON escapes newlines, so it is always one SSE data line.
    return f"id: {cursor}\nevent: {row['type']}\ndata: {data}\n\n"
