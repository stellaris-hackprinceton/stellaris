"""SQLite persistence for shared project metadata."""

import os
import sqlite3
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id                TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    description       TEXT NOT NULL,
    research_question TEXT,
    status            TEXT NOT NULL CHECK (status IN ('active', 'archived')),
    revision          INTEGER NOT NULL,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    -- Internal only. A project is publicly visible only once runtime_state = 'ready'.
    runtime_state     TEXT NOT NULL CHECK (runtime_state IN ('provisioning', 'ready', 'failed')),
    runtime_error     TEXT
);
CREATE INDEX IF NOT EXISTS projects_listing
    ON projects (runtime_state, updated_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    scope            TEXT NOT NULL,
    key              TEXT NOT NULL,
    body_sha256      TEXT NOT NULL,
    state            TEXT NOT NULL CHECK (state IN ('in_progress', 'failed', 'complete')),
    resource_id      TEXT,
    response_status  INTEGER,
    response_body    TEXT,
    response_headers TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    PRIMARY KEY (scope, key)
);

CREATE TABLE IF NOT EXISTS events (
    project_id  TEXT NOT NULL REFERENCES projects (id),
    sequence    INTEGER NOT NULL,
    type        TEXT NOT NULL,
    run_id      TEXT,
    payload     TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    PRIMARY KEY (project_id, sequence)
);

-- Resource tables keep the public JSON object in `doc`; other columns are for
-- filtering, ordering, and internal bookkeeping only.

CREATE TABLE IF NOT EXISTS sources (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects (id),
    provider    TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    doc         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS sources_page ON sources (project_id, created_at, id);

CREATE TABLE IF NOT EXISTS experiments (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects (id),
    revision    INTEGER NOT NULL,
    created_at  TEXT NOT NULL,
    doc         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS experiments_page ON experiments (project_id, created_at, id);

CREATE TABLE IF NOT EXISTS claims (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects (id),
    run_id      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    doc         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS claims_page ON claims (project_id, created_at, id);

CREATE TABLE IF NOT EXISTS messages (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects (id),
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    created_at  TEXT NOT NULL,
    doc         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_page ON messages (project_id, created_at, id);

-- Only ready (immutable, stored) artifacts have rows.
CREATE TABLE IF NOT EXISTS artifacts (
    id            TEXT PRIMARY KEY,
    project_id    TEXT NOT NULL REFERENCES projects (id),
    kind          TEXT NOT NULL,
    experiment_id TEXT,
    run_id        TEXT,
    size_bytes    INTEGER NOT NULL,
    sha256        TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    doc           TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS artifacts_page ON artifacts (project_id, created_at, id);

CREATE TABLE IF NOT EXISTS uploads (
    id                   TEXT PRIMARY KEY,
    project_id           TEXT NOT NULL REFERENCES projects (id),
    request              TEXT NOT NULL,
    status               TEXT NOT NULL CHECK (status IN ('pending', 'uploaded', 'completed', 'failed', 'expired')),
    artifact_id          TEXT,
    -- Internal: the artifact ID reserved at creation so completion retries reuse one storage path.
    reserved_artifact_id TEXT NOT NULL,
    declared_size        INTEGER NOT NULL,
    received_bytes       INTEGER,
    received_sha256      TEXT,
    expires_at           TEXT NOT NULL,
    error                TEXT,
    error_status         INTEGER,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS uploads_project ON uploads (project_id, status);

-- Runs: `doc` is the public Run; `snapshot` is the immutable accepted input snapshot
-- (persisted before the run is enqueued); `warnings` feeds RunResults.
CREATE TABLE IF NOT EXISTS runs (
    id            TEXT PRIMARY KEY,
    project_id    TEXT NOT NULL REFERENCES projects (id),
    kind          TEXT NOT NULL CHECK (kind IN ('agent', 'analysis', 'report', 'paper_ingest')),
    experiment_id TEXT,
    status        TEXT NOT NULL CHECK (status IN ('queued', 'running', 'awaiting_approval', 'cancelling',
                                                  'succeeded', 'failed', 'cancelled')),
    created_at    TEXT NOT NULL,
    doc           TEXT NOT NULL,
    snapshot      TEXT NOT NULL,
    warnings      TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS runs_page ON runs (project_id, created_at, id);
CREATE INDEX IF NOT EXISTS runs_status ON runs (status);

CREATE TABLE IF NOT EXISTS measurements (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects (id),
    run_id      TEXT NOT NULL REFERENCES runs (id),
    series      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    doc         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS measurements_page ON measurements (project_id, run_id, created_at, id);

-- Normalized extracted paper text, keyed by the paper.json artifact (ADR-0002). Used to verify
-- that citation excerpts and locators come from the retrieved full text. Internal only.
CREATE TABLE IF NOT EXISTS paper_texts (
    artifact_id TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects (id),
    text        TEXT NOT NULL,
    locators    TEXT NOT NULL
);

-- Approvals (Contracts section 7). Public JSON in `doc`.
CREATE TABLE IF NOT EXISTS approvals (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects (id),
    run_id      TEXT NOT NULL REFERENCES runs (id),
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    doc         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS approvals_page ON approvals (project_id, created_at, id);
CREATE INDEX IF NOT EXISTS approvals_run ON approvals (run_id, status);

CREATE TABLE IF NOT EXISTS run_logs (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects (id),
    run_id      TEXT NOT NULL REFERENCES runs (id),
    sequence    INTEGER NOT NULL,
    created_at  TEXT NOT NULL,
    doc         TEXT NOT NULL,
    UNIQUE (run_id, sequence)
);
"""


def connect(path: str) -> sqlite3.Connection:
    # One connection per request/stream/worker thread; never share a connection across threads.
    # isolation_level=None: transactions are controlled explicitly with transaction().
    conn = sqlite3.connect(path, isolation_level=None, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def init_db(path: str) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = connect(path)
    try:
        _migrate_run_kinds(conn)
        conn.executescript(SCHEMA)
    finally:
        conn.close()


def _migrate_run_kinds(conn: sqlite3.Connection) -> None:
    """Rebuild a pre-1.1 runs table whose CHECK constraint lacks 'paper_ingest'.

    SQLite cannot alter a CHECK constraint, so the table is copied into the current schema
    (SQLite's documented 12-step procedure, with foreign keys disabled during the swap).
    """
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'runs'").fetchone()
    if row is None or "paper_ingest" in row["sql"]:
        return
    runs_ddl = SCHEMA[SCHEMA.index("CREATE TABLE IF NOT EXISTS runs ("):]
    runs_ddl = runs_ddl[:runs_ddl.index(");") + 2].replace("CREATE TABLE IF NOT EXISTS runs (",
                                                              "CREATE TABLE runs_migrated (")
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        with transaction(conn):
            conn.execute(runs_ddl)
            conn.execute("INSERT INTO runs_migrated (id, project_id, kind, experiment_id, status, created_at, doc, "
                         "snapshot, warnings) SELECT id, project_id, kind, experiment_id, status, created_at, doc, "
                         "snapshot, warnings FROM runs")
            conn.execute("DROP TABLE runs")
            conn.execute("ALTER TABLE runs_migrated RENAME TO runs")
            problems = conn.execute("PRAGMA foreign_key_check").fetchall()
            if problems:
                raise sqlite3.IntegrityError(f"runs migration broke {len(problems)} foreign key references")
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


@contextmanager
def transaction(conn: sqlite3.Connection, immediate: bool = True):
    conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
