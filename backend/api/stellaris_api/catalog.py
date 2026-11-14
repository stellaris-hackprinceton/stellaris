"""Per-project workspace file catalogs (docs/file-workspace-contract.md; plan slice 1).

Storage: one SQLite file per project, <catalog_dir>/<project_id>.sqlite3, on the API's own
persistent volume. It is backend-owned and never mounted into project or worker containers.
Artifact bytes stay in the project volume and are never copied here.

Consistency model:
  * The main database stays authoritative and its write paths are unchanged. Before serving
    a catalog route, sync() projects any legacy change into the catalog (lazy backfill).
  * A pass reads legacy state inside ONE main-DB read transaction, closes it, then writes
    the catalog in one BEGIN IMMEDIATE transaction together with a `catalog.changed`
    outbox row. No main-DB transaction is ever open while the catalog is written, and vice
    versa, so the two databases cannot deadlock.
  * relay() copies outbox rows into the main event stream after commit (and at startup).
    A crash between the two commits can duplicate an event, never a mutation; the event
    contract is at-least-once.
  * A catalog that fails `PRAGMA quick_check`, belongs to another project, or cannot be
    opened is reported as unavailable (503). It is never renamed, replaced, or deleted.
"""

import json
import logging
import os
import re
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

from . import catalog_projection as proj
from . import db
from .db import transaction
from .events import record_event
from .http import TIMESTAMP_FORMAT, dumps, now_ts

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1
PROJECT_ID = re.compile(r"^prj_[0-9a-f]{32}$")
_CATALOG_FILE = re.compile(r"^(prj_[0-9a-f]{32})\.sqlite3$")
MAX_EVENT_CHANGES = 100
RELAY_BATCH = 100
OUTBOX_RETENTION_S = 24 * 3600
SYNC_ERROR = {"code": "SYNC_FAILED",
              "message": "Projecting legacy records into the file catalog failed. Retry later; details are in the server log."}

# The full v1 schema is created at once so later slices need no migration.
SCHEMA = (
    "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    """CREATE TABLE IF NOT EXISTS files (
        id                TEXT PRIMARY KEY,
        file_kind         TEXT NOT NULL CHECK (file_kind IN ('artifact', 'record', 'note')),
        origin_type       TEXT,
        origin_id         TEXT,
        origin_revision   INTEGER,
        name              TEXT NOT NULL,
        name_key          TEXT NOT NULL,
        mime_type         TEXT NOT NULL,
        size_bytes        INTEGER NOT NULL,
        content_sha256    TEXT NOT NULL,
        scientific_origin TEXT,
        status            TEXT NOT NULL CHECK (status IN ('active', 'trashed')),
        content_revision  INTEGER,
        render_version    INTEGER,
        revision          INTEGER NOT NULL,
        created_at        TEXT NOT NULL,
        updated_at        TEXT NOT NULL,
        UNIQUE (origin_type, origin_id)
    )""",
    "CREATE INDEX IF NOT EXISTS files_created ON files (created_at, id)",
    "CREATE INDEX IF NOT EXISTS files_updated ON files (updated_at, id)",
    "CREATE INDEX IF NOT EXISTS files_name ON files (name_key, id)",
    "CREATE INDEX IF NOT EXISTS files_kind ON files (file_kind)",
    "CREATE INDEX IF NOT EXISTS files_status ON files (status)",
    """CREATE TABLE IF NOT EXISTS note_revisions (
        file_id TEXT NOT NULL REFERENCES files (id), content_revision INTEGER NOT NULL, name TEXT NOT NULL,
        mime_type TEXT NOT NULL, content TEXT NOT NULL, size_bytes INTEGER NOT NULL, sha256 TEXT NOT NULL,
        created_at TEXT NOT NULL, PRIMARY KEY (file_id, content_revision)
    )""",
    """CREATE TABLE IF NOT EXISTS tags (
        slug TEXT PRIMARY KEY, label TEXT NOT NULL, color TEXT, system INTEGER NOT NULL,
        revision INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS file_tags (
        file_id TEXT NOT NULL REFERENCES files (id), slug TEXT NOT NULL REFERENCES tags (slug),
        assigned_by TEXT NOT NULL CHECK (assigned_by IN ('system', 'user')), created_at TEXT NOT NULL,
        PRIMARY KEY (file_id, slug)
    )""",
    "CREATE INDEX IF NOT EXISTS file_tags_slug ON file_tags (slug, file_id)",
    """CREATE TABLE IF NOT EXISTS collections (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL, filter TEXT,
        revision INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS collection_files (
        collection_id TEXT NOT NULL REFERENCES collections (id), file_id TEXT NOT NULL REFERENCES files (id),
        added_at TEXT NOT NULL, PRIMARY KEY (collection_id, file_id)
    )""",
    "CREATE INDEX IF NOT EXISTS collection_files_file ON collection_files (file_id)",
    """CREATE TABLE IF NOT EXISTS relations (
        id TEXT PRIMARY KEY, from_file_id TEXT NOT NULL REFERENCES files (id),
        to_file_id TEXT NOT NULL REFERENCES files (id), type TEXT NOT NULL, note TEXT,
        created_by TEXT NOT NULL CHECK (created_by IN ('user', 'system')), created_at TEXT NOT NULL,
        UNIQUE (from_file_id, to_file_id, type)
    )""",
    "CREATE INDEX IF NOT EXISTS relations_from ON relations (from_file_id)",
    "CREATE INDEX IF NOT EXISTS relations_to ON relations (to_file_id)",
    """CREATE TABLE IF NOT EXISTS idempotency_keys (
        scope TEXT NOT NULL, key TEXT NOT NULL, body_sha256 TEXT NOT NULL,
        state TEXT NOT NULL CHECK (state IN ('in_progress', 'failed', 'complete')),
        resource_id TEXT, response_status INTEGER, response_body TEXT, response_headers TEXT,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY (scope, key)
    )""",
    """CREATE TABLE IF NOT EXISTS outbox (
        id INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT NOT NULL, created_at TEXT NOT NULL, relayed_at TEXT
    )""",
)

# Columns a projection pass may update. User-owned state (user tags, status, notes,
# collections, relations) is never touched by projection.
PROJECTED_COLUMNS = ("name", "name_key", "mime_type", "size_bytes", "content_sha256", "scientific_origin",
                     "origin_revision", "render_version", "created_at", "updated_at")


class CatalogUnavailable(Exception):
    """The catalog cannot be used. Message is for logs only, never for API responses."""


class SyncFailed(Exception):
    """A projection pass failed and was rolled back."""


_lock = threading.Lock()
_project_locks = {}
_checked = set()


def _project_lock(project_id: str) -> threading.Lock:
    with _lock:
        return _project_locks.setdefault(project_id, threading.Lock())


# -- storage -------------------------------------------------------------------------------

def catalog_path(config, project_id: str) -> str:
    if not isinstance(project_id, str) or not PROJECT_ID.fullmatch(project_id):
        raise CatalogUnavailable("invalid project id for a catalog path")
    return os.path.join(config.catalog_dir, f"{project_id}.sqlite3")


def open_catalog(config, project_id: str, *, create: bool = True):
    """Open (creating lazily if `create`) a project's catalog. Returns None when absent and not
    creating. Raises CatalogUnavailable; the caller closes the returned connection."""
    path = catalog_path(config, project_id)
    if not create and not os.path.exists(path):
        return None
    try:
        os.makedirs(config.catalog_dir, mode=0o700, exist_ok=True)
    except OSError as exc:
        raise CatalogUnavailable(f"catalog directory unavailable: {exc}") from exc
    conn = None
    try:
        conn = db.connect(path)
        with _lock:
            first_open = path not in _checked
        if first_open:
            result = conn.execute("PRAGMA quick_check").fetchone()[0]
            if result != "ok":
                raise CatalogUnavailable(f"quick_check failed for {project_id}: {str(result)[:200]}")
        _ensure_schema(conn, project_id, seed=first_open)
        if first_open:
            with _lock:
                _checked.add(path)
        return conn
    except CatalogUnavailable:
        if conn is not None:
            conn.close()
        raise
    except sqlite3.Error as exc:
        if conn is not None:
            conn.close()
        raise CatalogUnavailable(f"catalog for {project_id} could not be opened: {type(exc).__name__}: {exc}") from exc


def _ensure_schema(conn, project_id: str, *, seed: bool) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise CatalogUnavailable(f"catalog for {project_id} has newer schema version {version}")
    if version == 0 or seed:
        with transaction(conn):
            ts = now_ts()
            if conn.execute("PRAGMA user_version").fetchone()[0] == 0:
                for statement in SCHEMA:
                    conn.execute(statement)
                conn.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('project_id', ?)", (project_id,))
                conn.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('created_at', ?)", (ts,))
                conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            for slug in proj.SYSTEM_TAGS:  # Idempotent; also adds default tags introduced later.
                conn.execute("INSERT OR IGNORE INTO tags (slug, label, color, system, revision, created_at, updated_at) "
                             "VALUES (?, ?, NULL, 1, 1, ?, ?)", (slug, slug, ts, ts))
    if meta_get(conn, "project_id") != project_id:
        raise CatalogUnavailable(f"catalog file for {project_id} belongs to a different project")


def meta_get(conn, key: str):
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def _meta_set(conn, key: str, value) -> None:
    if value is None:
        conn.execute("DELETE FROM meta WHERE key = ?", (key,))
    else:
        conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                     (key, str(value)))


# -- projection ------------------------------------------------------------------------------

def sync(main, cat, project_id: str) -> None:
    """Bring the catalog up to date with every legacy change committed before this call.

    `main` must have no open transaction. Raises SyncFailed (catalog changes rolled back,
    safe error recorded). Relays pending catalog events afterwards (best effort).
    """
    with _project_lock(project_id):
        try:
            _sync_locked(main, cat, project_id)
        except Exception as exc:
            log.exception("Catalog projection failed for %s", project_id)
            try:
                with transaction(cat):
                    _meta_set(cat, "last_sync_error", dumps(SYNC_ERROR))
            except Exception:
                log.warning("Could not record the projection failure for %s", project_id)
            raise SyncFailed() from exc
        relay(main, cat, project_id)


def _sync_locked(main, cat, project_id: str) -> None:
    projected = {(r["origin_type"], r["origin_id"]): (r["origin_revision"], r["render_version"])
                 for r in cat.execute("SELECT origin_type, origin_id, origin_revision, render_version FROM files "
                                      "WHERE origin_type IS NOT NULL")}
    synced = meta_get(cat, "synced_event_sequence")
    rendered = meta_get(cat, "render_version")
    with transaction(main, immediate=False):  # One consistent legacy snapshot; committed before any write.
        sequence = proj.legacy_sequence(main, project_id)
        if synced == str(sequence) and rendered == str(proj.RENDER_VERSION) and meta_get(cat, "last_sync_error") is None:
            return
        entries = proj.collect(main, project_id, projected)
    with transaction(cat):
        changes = [c for c in (_upsert(cat, e) for e in entries) if c]
        _meta_set(cat, "synced_event_sequence", sequence)
        _meta_set(cat, "render_version", proj.RENDER_VERSION)
        _meta_set(cat, "last_synced_at", now_ts())
        _meta_set(cat, "last_sync_error", None)
        if changes:
            if len(changes) > MAX_EVENT_CHANGES:
                changes = [{"entity": "file", "id": None, "revision": None, "deleted": False, "bulk": True}]
            enqueue_event(cat, changes)


def _upsert(cat, entry: dict):
    """Insert or refresh one projected file plus its system tags. Returns a CatalogChange or None."""
    row = cat.execute("SELECT * FROM files WHERE origin_type = ? AND origin_id = ?",
                      (entry["origin_type"], entry["origin_id"])).fetchone()
    if row is None:
        cat.execute(
            "INSERT INTO files (id, file_kind, origin_type, origin_id, origin_revision, name, name_key, mime_type, "
            "size_bytes, content_sha256, scientific_origin, status, content_revision, render_version, revision, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', NULL, ?, 1, ?, ?)",
            (entry["id"], entry["file_kind"], entry["origin_type"], entry["origin_id"], entry["origin_revision"],
             entry["name"], entry["name_key"], entry["mime_type"], entry["size_bytes"], entry["content_sha256"],
             entry["scientific_origin"], entry["render_version"], entry["created_at"], entry["updated_at"]),
        )
        _assign_system_tags(cat, entry)
        return {"entity": "file", "id": entry["id"], "revision": 1, "deleted": False}
    if row["id"] != entry["id"]:
        raise RuntimeError(f"catalog file {row['id']} does not have its deterministic id {entry['id']}")
    changed = {c: entry[c] for c in PROJECTED_COLUMNS if row[c] != entry[c]}
    tags_changed = _assign_system_tags(cat, entry)
    if not changed and not tags_changed:
        return None
    revision = row["revision"] + 1
    assignments = "".join(f"{column} = ?, " for column in changed)
    cat.execute(f"UPDATE files SET {assignments}revision = ? WHERE id = ?", [*changed.values(), revision, row["id"]])
    return {"entity": "file", "id": row["id"], "revision": revision, "deleted": False}


def _assign_system_tags(cat, entry: dict) -> bool:
    """Add missing system assignments; an existing user assignment of the same slug becomes system."""
    changed = False
    for slug in entry["tags"]:
        cursor = cat.execute(
            "INSERT INTO file_tags (file_id, slug, assigned_by, created_at) VALUES (?, ?, 'system', ?) "
            "ON CONFLICT (file_id, slug) DO UPDATE SET assigned_by = 'system' WHERE assigned_by = 'user'",
            (entry["id"], slug, now_ts()),
        )
        changed = changed or cursor.rowcount > 0
    return changed


# -- events ----------------------------------------------------------------------------------

def enqueue_event(cat, changes: list) -> None:
    """Add a catalog.changed payload to the outbox inside the caller's catalog transaction."""
    cat.execute("INSERT INTO outbox (payload, created_at) VALUES (?, ?)", (dumps({"changes": changes}), now_ts()))


def relay(main, cat, project_id: str) -> None:
    """Copy pending outbox rows into the main event stream (best effort; retried later).

    Caller holds the project lock. Each row is written to the main DB and committed before
    it is marked relayed in the catalog, so a crash may duplicate one event but never loses it.
    """
    try:
        rows = cat.execute("SELECT id, payload FROM outbox WHERE relayed_at IS NULL ORDER BY id LIMIT ?",
                           (RELAY_BATCH,)).fetchall()
        for row in rows:
            with transaction(main):
                record_event(main, project_id, proj.CATALOG_EVENT, json.loads(row["payload"]))
            with transaction(cat):
                cat.execute("UPDATE outbox SET relayed_at = ? WHERE id = ? AND relayed_at IS NULL", (now_ts(), row["id"]))
        if rows:
            cutoff = (datetime.now(timezone.utc) - timedelta(seconds=OUTBOX_RETENTION_S)).strftime(TIMESTAMP_FORMAT)
            with transaction(cat):
                cat.execute("DELETE FROM outbox WHERE relayed_at IS NOT NULL AND relayed_at < ?", (cutoff,))
    except Exception:
        log.exception("Relaying catalog events failed for %s; they remain pending", project_id)


def relay_all(config) -> None:
    """Startup: relay pending events of existing catalogs. Never creates a catalog."""
    if not os.path.isdir(config.catalog_dir):
        return
    main = db.connect(config.db_path)
    try:
        ready = {r["id"] for r in main.execute("SELECT id FROM projects WHERE runtime_state = 'ready'")}
        for name in sorted(os.listdir(config.catalog_dir)):
            match = _CATALOG_FILE.fullmatch(name)
            if not match or match.group(1) not in ready:
                continue
            project_id = match.group(1)
            try:
                cat = open_catalog(config, project_id, create=False)
            except CatalogUnavailable as exc:
                log.error("Catalog unavailable at startup: %s", exc)
                continue
            if cat is None:
                continue
            try:
                with _project_lock(project_id):
                    relay(main, cat, project_id)
            finally:
                cat.close()
    finally:
        main.close()


# -- status ----------------------------------------------------------------------------------

def status(cat, config) -> dict:
    projected = {origin_type: 0 for origin_type in proj.ORIGIN_TYPES}
    for row in cat.execute("SELECT origin_type, COUNT(*) AS n FROM files WHERE origin_type IS NOT NULL "
                           "GROUP BY origin_type"):
        if row["origin_type"] in projected:
            projected[row["origin_type"]] = row["n"]
    notes = cat.execute("SELECT COUNT(*) FROM files WHERE file_kind = 'note'").fetchone()[0]
    note_bytes = cat.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM note_revisions").fetchone()[0]
    error = meta_get(cat, "last_sync_error")
    return {
        "schema_version": cat.execute("PRAGMA user_version").fetchone()[0],
        "workspace_files": True,
        "last_synced_at": meta_get(cat, "last_synced_at"),
        "projected": projected,
        "notes": {"count": notes, "retained_bytes": note_bytes, "max_bytes": config.max_note_bytes},
        "last_sync_error": json.loads(error) if error else None,
    }
