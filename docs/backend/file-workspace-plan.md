# File workspace implementation plan

Interface: [../file-workspace-contract.md](../file-workspace-contract.md) (proposed, additive to `/api/v1`).
Status: **slice 1 implemented and Docker-verified; slices 2–4 pending.** Prepared 2026-11-14 on branch `backend-v2`.

## Goal and boundaries

Add a project-scoped file catalog: every artifact and legacy scientific record appears as a
file, legacy categories become default tags, users get tags, mutable notes with revisions,
collections, and explicit relations. Later UI (graph view, richer explorer) builds on this.

In scope: catalog storage, idempotent projection/backfill, read and mutation routes, one new
`catalog.changed` event, a capability flag, and one Docker integration script.

Out of scope (do not build): folders, full-text/semantic search, embeddings or inferred
links, graph endpoints/visualization, agent tools for notes/tags, file hard deletion,
frontend changes, changes to legacy routes or tables.

## Verified facts this plan relies on

Read from source on 2026-11-14 (not from the draft contract):

- Main DB: one SQLite file `STELLARIS_DB_PATH=/data/stellaris.sqlite3` on the named Compose
  volume `stellaris-api-data` (`backend/compose.yaml`), WAL, explicit `BEGIN IMMEDIATE`
  transactions (`db.py`). Resource tables store the public JSON in `doc`.
- `sources`, `claims`, `artifacts`, `measurements` rows are insert-only (no `UPDATE`/`DELETE`
  statements exist for them). `experiments.doc` and `runs.doc` are updated in place;
  experiments carry `revision`; runs reach `TERMINAL = (succeeded, failed, cancelled)`.
- Every legacy write records a project event in the same transaction (`events.record_event`);
  `events.latest_sequence()` is monotonic per project and purging keeps the newest row.
- Artifact bytes live only in the project volume at `/workspace/data/artifacts/<art_id>`
  (root-owned 0444) and move solely through the Docker archive API (`runtime.py`).
  `/workspace/scratch` is the agent's private space. The API has no filesystem path into
  project volumes.
- Run logs and provenance are already immutable artifacts (`run-log.txt`,
  `agent-run-log.txt`, `provenance.json`, kinds `log`/`environment`). Measurements, sources,
  claims, and experiments exist only as DB rows.
- `idempotency.run_command/claim/begin/complete` operate on any connection with an
  `idempotency_keys` table of the same shape; scope is `"METHOD path"`.
- `http.project_page` is table-generic but hard-codes `(created_at, id)` order; projects use
  a custom cursor. JSON request bodies are capped at 1 MiB (`MAX_CONTENT_LENGTH`).
- The API runs a single Gunicorn process (`artifacts.py` docstring); no automated test suite
  exists beyond `backend/scripts/*.py` Docker checks.

## Key design decisions

1. **Per-project catalog SQLite owned by the backend, on the API volume.**
   `STELLARIS_CATALOG_DIR` (default `/data/catalogs`), one file per project:
   `/data/catalogs/<project_id>.sqlite3` (+ WAL/SHM), directory mode 0700, path built only
   after `project_id` matches `^prj_[0-9a-f]{32}$`. Rejected alternative: storing the
   catalog in the project volume. SQLite needs local file locking and journal files; the API
   could reach it only through Docker exec/archive copies (unsafe remote DB access), and the
   project runtime user could tamper with it. Consequence (documented): a full project
   backup needs both `stellaris-api-data` (catalog, main DB) and the project volume
   (artifact bytes). Original artifacts stay in the project volume, untouched.
2. **Lazy, reconciled projection, no migration of legacy tables.** Legacy write paths are
   not modified. Before serving any catalog route, `catalog.sync(project_id)` compares the
   main DB's `latest_sequence` with the catalog's stored `synced_event_sequence`; if equal
   (and renderer version current) it is a no-op. Otherwise it diffs legacy IDs against
   projected origins and upserts. Deterministic IDs
   (`fil_`/`rel_` + first 32 hex of `sha256("stellaris-file:{project}:{type}:{id}")`) plus
   `UNIQUE(origin_type, origin_id)` make backfill, re-runs, and rebuilds idempotent.
3. **Record files are rendered, not stored.** Sources, claims, experiments, terminal runs,
   and per-run measurements render deterministically from legacy `doc`s (contract §5);
   the catalog stores only name, size, SHA-256, renderer version, and origin revision. No
   evidence is copied or duplicated; artifact files stream the original bytes by
   delegating to the existing artifact content handler.
4. **Notes live in the catalog** (`note_revisions`, append-only), never in the project
   volume or `artifacts`, so they cannot be mistaken for evidence and do not consume the
   artifact quota. Separate budget `STELLARIS_MAX_NOTE_BYTES` (default 64 MiB).
5. **Atomicity within the catalog; outbox for events.** Catalog mutations, their
   idempotency rows (catalog-local `idempotency_keys`, reusing `idempotency.py`), and an
   `outbox` row commit in one catalog transaction. After commit (and during each sync and at
   startup) a relay inserts outbox payloads as `catalog.changed` events in the main DB,
   then marks them relayed. A crash between the two duplicates at most one event, which the
   at-least-once event contract already permits. No cross-database transaction is assumed
   (SQLite ATTACH is not atomic across files in WAL mode).
6. **Tags are organizational only.** `file_tags.assigned_by` separates system (projection)
   from user assignments; clients can never remove system assignments, and system relation
   types are reserved so users cannot forge provenance edges.
7. **Concurrency.** Per-project `threading.Lock` around sync (single process), plus
   `BEGIN IMMEDIATE` on the catalog for every write; legacy reads for sync happen inside one
   deferred main-DB read transaction so the snapshot matches the recorded sequence.

## Catalog schema (v1, `PRAGMA user_version = 1`)

```sql
meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)
  -- project_id, created_at, synced_event_sequence, render_version, last_synced_at, last_sync_error
files(id TEXT PRIMARY KEY, file_kind TEXT CHECK (file_kind IN ('artifact','record','note')),
      origin_type TEXT, origin_id TEXT, origin_revision INTEGER,
      name TEXT NOT NULL, name_key TEXT NOT NULL, mime_type TEXT NOT NULL,
      size_bytes INTEGER NOT NULL, content_sha256 TEXT NOT NULL,
      scientific_origin TEXT, status TEXT NOT NULL CHECK (status IN ('active','trashed')),
      content_revision INTEGER, render_version INTEGER, revision INTEGER NOT NULL,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      UNIQUE (origin_type, origin_id))
  + indexes (created_at,id), (updated_at,id), (name_key,id), (file_kind), (status)
note_revisions(file_id, content_revision, name, mime_type, content TEXT, size_bytes,
               sha256, created_at, PRIMARY KEY (file_id, content_revision))
tags(slug PRIMARY KEY, label, color, system INTEGER, revision, created_at, updated_at)
file_tags(file_id, slug, assigned_by CHECK IN ('system','user'), created_at,
          PRIMARY KEY (file_id, slug))  + index (slug, file_id)
collections(id PRIMARY KEY, name, description, filter TEXT, revision, created_at, updated_at)
collection_files(collection_id, file_id, added_at, PRIMARY KEY (collection_id, file_id))
  + index (file_id)
relations(id PRIMARY KEY, from_file_id, to_file_id, type, note, created_by
          CHECK IN ('user','system'), created_at, UNIQUE (from_file_id, to_file_id, type))
  + indexes (from_file_id), (to_file_id)
idempotency_keys(...)   -- identical to backend/api/stellaris_api/db.py
outbox(id INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT NOT NULL, created_at TEXT NOT NULL,
       relayed_at TEXT)
```

Future schema changes are additive and gated by `user_version`; never drop user tables.

## Slices

Each slice is independently mergeable, keeps legacy behavior byte-for-byte, and ends with its
acceptance commands. Write scopes are disjoint per slice so they can be delegated one at a time.

### Slice 1 — Catalog foundation, projection/backfill, read API

Files: new `backend/api/stellaris_api/catalog.py` (path, connect, schema, integrity check,
deterministic IDs, renderers, `sync()`, outbox relay); new
`backend/api/stellaris_api/files.py` (blueprint: `GET /catalog`, `GET /files`,
`GET /files/{id}`, `GET /files/{id}/content`, `GET /tags`, `GET /tags/{slug}`);
`config.py` (`catalog_dir`, `max_note_bytes`); `app.py` (register blueprint, add
`features.workspace_files: true`, relay pending outboxes for existing catalog files in the
reconcile thread); new `backend/scripts/workspace_files_test.py`; optionally
`artifacts.py`, limited to a behavior-preserving extraction of the content-streaming helper.

Status (2026-11-14): code written, **not yet built or tested**. Boxes stay unchecked until
`workspace_files_test.py --slice 1` and the legacy regression scripts pass. Modules:
`catalog.py` (storage, schema, sync, outbox relay), `catalog_projection.py` (legacy snapshot
reads, deterministic IDs, renderers), and `files.py` (routes). `features.workspace_files` is
`true` but means the **read foundation only**: `GET /catalog`, `/files`, `/files/{id}`,
`/files/{id}/content`, `/tags`, and `/tags/{slug}`. Every mutation route in the contract is
unregistered (405/404) until slices 2–3. Implementation notes:
- The legacy change check ignores relayed `catalog.changed` events (`type != 'catalog.changed'`),
  so the catalog's own events never trigger another projection pass.
- Artifact content is served by calling `artifacts.artifact_content` directly. `artifacts.py`
  is unchanged.
- Terminal runs are re-projected only if their `doc.revision` changes (read with
  `json_extract`). Measurements are rendered once their analysis run is terminal.
- The full v1 schema, including tables for slices 2–3, is created up front, so later
  slices need no migration.

- [x] Catalog file created lazily for visible (`runtime_state = 'ready'`) projects only;
      `PRAGMA quick_check` on first open per process; failure returns 503 without renaming, replacing or deleting the catalog.
- [x] Default tags seeded on creation (contract §6).
- [x] `sync()` projects artifacts, sources, claims, experiments (re-render on revision
      change), terminal runs (Run + `runs.results()`), measurements of terminal analysis
      runs with ≥1 row; assigns system tags (agent vs other run logs via `runs.kind`).
- [x] Record renderers deterministic (sorted keys, indent 2, trailing newline; CSV columns
      per contract); `RENDER_VERSION` constant re-renders older rows.
- [x] Projected `created_at` = legacy `created_at`; `scientific_origin` per contract §4.
- [x] `GET /files` filters, sorts, and cursors per contract §8 (own cursor encoder bound to
      route, project, sort, order, filters; reuse `encode_cursor`/`decode_cursor`).
- [x] Artifact-file content delegates to `artifacts.artifact_content(project_id, artifact_id)`
      (Range/ETag/CSP preserved); record content rendered on demand.
- [x] Projection pass that changes files writes one bulk/compact `catalog.changed` outbox row;
      relay after commit.

Acceptance:

```bash
python3 -m py_compile backend/api/stellaris_api/*.py
docker compose -f backend/compose.yaml --profile build-only build
docker compose -f backend/compose.yaml up -d --wait --force-recreate api
(cd backend && python3 scripts/workspace_files_test.py --slice 1)
(cd backend && python3 scripts/smoke_test.py && python3 scripts/integration_test.py)
```

Script checks (observable): an existing project created before this slice backfills on first
`GET /catalog`; projected counts equal legacy counts (artifacts, sources, claims,
experiments, terminal runs, runs with measurements); a second sync and an API restart yield
identical file IDs and counts (no duplicates); deleting the catalog file (test project only,
inside the api container) rebuilds identical artifact/record IDs; artifact-file content
bytes/SHA equal `/artifacts/{id}/content`; a 206 range works through `/files/.../content`;
record JSON `data` equals the legacy GET body; an experiment PATCH changes the file's
`origin.revision` and SHA on next read; simulated measurements keep `data_origin` and file
`scientific_origin: "simulated"`; another project's file ID returns 404; legacy endpoints and
`Workspace.counts` unchanged.

### Slice 2 — Notes, tags, tagging, events

Files: `files.py` (POST `/files`, PATCH `/files/{id}`, `GET /files/{id}/revisions`,
`?revision=` content, POST `/files/tagging`, POST/PATCH/DELETE `/tags`); `catalog.py`
(note/tag helpers, quota, validation); `workspace_files_test.py` (`--slice 2`).

- [ ] Every POST via `idempotency.run_command(catalog_conn, …)`; PATCH/DELETE `If-Match`
      with 428/412 semantics identical to projects/experiments.
- [ ] Note validation (name rules = `artifacts.filename_error`, UTF-8, no NUL, 512 KiB,
      project note budget → 413); identical content creates no revision.
- [ ] `FILE_READ_ONLY` for name/content/status on artifact/record files; system assignments
      immutable (422); reserved behavior for system tags (`TAG_PROTECTED`).
- [ ] `load_writable` (main DB) checked before each mutation → `409 PROJECT_ARCHIVED`.
- [ ] Outbox row per mutation in the same catalog transaction; relay emits
      `catalog.changed`; verified on the SSE stream.

Acceptance: slice 1 commands plus `(cd backend && python3 scripts/workspace_files_test.py --slice 2)`.
Script checks: create note → revision 1; PATCH content with stale ETag → 412, without →
428; older revision downloadable via `?revision=1`; same Idempotency-Key replays with
`Idempotent-Replayed: true`, different body → 409; tagging batch adds/removes user tags,
system removal → 422; tag filter AND semantics; archived project → 409 for every mutation;
`catalog.changed` observed after `after=<cursor>`; notes do not appear in `/artifacts`,
`Workspace.counts`, or as accepted evidence/run inputs.

### Slice 3 — Collections and relations (user + recorded provenance)

Files: `files.py` (collections and relations routes); `catalog.py` (system relation
projection, limits); `workspace_files_test.py` (`--slice 3`).

- [ ] Collections CRUD with optional saved filter, set-membership add/remove for explicit collections, `GET /files?collection_id=`; deleting a
      collection never touches files.
- [ ] User relations: directed, no self-loops, duplicate triple returns 200 existing, reserved
      system types rejected, cross-project IDs → 422.
- [ ] System relations projected during sync from `parent_artifact_ids`, `run_id`
      (`produced_by`, once the run file exists), claim citations and evidence/measurements;
      deterministic IDs; `RELATION_PROTECTED` on delete.
- [ ] `GET /relations` filters `file_id` + `direction`, `type`, `created_by`, paged.

Acceptance: slice 1 commands plus `(cd backend && python3 scripts/workspace_files_test.py --slice 3)`.
Script checks: report artifact `derived_from` its chart/measurement inputs exactly as
recorded in `parent_artifact_ids` and no other system edges appear; re-sync creates no
duplicate edges; user relation round-trip and direction filters; collection membership
idempotent; limits return 422.

### Slice 4 — Documentation and verification close-out (docs only)

- [ ] Mark contract status per implemented slice; record actual check counts in
      `docs/backend/verification.md`; update `docs/backend/README.md` (catalog location,
      backup note, recovery procedure) and `docs/backend/implementation-plan.md`.
- [ ] Hand the contract to frontend teammates; frontend work is a separate, authorized task.

## Compatibility and recovery

- No legacy table, route, response field, event payload, or status code changes. Removing
  `files.py`'s blueprint and the capability flag fully disables the feature; catalog files
  can stay on disk unused.
- Rollback to the pre-feature backend leaves catalogs untouched and ignored.
- Corrupt catalogs fail with 503 and remain untouched; restore from a backup. Absent catalogs
  rebuild projected files with stable IDs, but notes/user metadata require the API volume backup.
- Sync failures roll back and return 503 on file/tag/collection/relation routes. Catalog status
  may report the safe last_sync_error with 200, but does not assert fresh projection.
- Main-DB event purge does not affect sync (uses only the max sequence and ID diffs).

## Uncertainties to resolve during implementation

- Diff-based sync scans all project legacy IDs whenever the event sequence moves (including
  after the catalog's own relayed events). Expected fine at MVP scale; add per-type
  high-water marks only if measured to be slow.
- `artifacts.artifact_content` is a Flask view called directly for delegation; if that proves
  awkward, extract its body into a shared helper inside slice 1's `artifacts.py` edit
  (the only permitted legacy-module change: a pure refactor with identical behavior).
- Measurements CSV size is bounded only by worker output limits; if rendering exceeds
  16 MiB, mark the file unavailable (`503` on content) rather than truncating silently —
  confirm with the user if this occurs.
- Whether the frontend wants `collection_ids` on every file (cost: one indexed query per
  page) — kept in the contract; drop only via contract amendment.

Verification checkpoint: Slice 1 passed 76 Docker/API integration checks, including the malformed tag cursor regression. No paid model calls.
