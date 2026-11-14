# Stellaris backend

Flask API, SQLite metadata, and one dynamically created Docker container plus persistent
named volume per project. Implemented: projects, manual sources, claims (read), experiments,
uploads/artifacts stored in the project volume, and project SSE events. Agent chat and
scientific runs are not implemented yet. See `IMPLEMENTATION_PLAN.md` for status and
`../Contracts.md` for the API contract.

## Layout

```
compose.yaml                 single Compose config (api service + build-only runtime image)
api/                         primary backend (Flask, sqlite3, Docker SDK, Gunicorn, ffprobe)
project_runtime/             per-project container image (workspace + /health; Deep Agents next)
scripts/smoke_test.py        slice 1 Docker smoke test (projects, containers, restarts)
scripts/integration_test.py  slice 2 checks (sources, experiments, uploads, ranges, isolation, SSE, ETags)
```

## Start

Requires Docker (Docker Desktop on macOS) and Compose v2.24+ (optional `env_file`).

```bash
cd backend
cp -n .env.example .env          # then fill in values yourself; never commit .env
docker compose --profile build-only build   # builds stellaris-api:dev and stellaris-project-runtime:dev
docker compose up -d
curl -s http://127.0.0.1:8000/api/v1/health
```

The API listens on `127.0.0.1:8000` only. There is no authentication in this development mode.

Create a project (this creates and starts its container):

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/projects \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: demo-1' \
  -d '{"name":"Bouncing ball","research_question":"How much energy is lost per bounce?"}'
docker ps --filter label=stellaris.managed=true
```

## Verify

```bash
cd backend
docker compose --profile build-only build && docker compose up -d
python3 scripts/smoke_test.py            # includes api + project-container restarts
python3 scripts/smoke_test.py --skip-restart
python3 scripts/integration_test.py      # ~16 s idle wait for the SSE heartbeat check
python3 scripts/integration_test.py --skip-heartbeat
docker compose logs api
```

`integration_test.py` uses only generated fixtures (a gradient PNG, a 1 s ffmpeg `testsrc`
clip produced inside the api container, a CSV), all uploaded with origin `simulated` and
`SIMULATED-` filenames. It never presents them as observed data.

After changing `project_runtime/`, rebuild with the `build-only` profile. Existing project
containers keep their old image until removed; the backend recreates a removed container
on its existing volume at the next API start (`docker rm -f stellaris-<id>` then
`docker compose restart api`).

## Architecture notes

- **Control plane.** Only the `api` container mounts the Docker socket. It creates, for project
  `prj_x`: volume `stellaris-prj_x-workspace` (mounted at `/workspace`, with `data/` and
  `scratch/`) and container `stellaris-prj_x`. Both carry `stellaris.project_id` labels.
- **Project containers.** Non-root (uid 10001), read-only root filesystem, `cap_drop: ALL`,
  `no-new-privileges`, memory/CPU/PID limits, no published ports, no bind mounts, no Docker
  socket, `restart: unless-stopped`. They join the `stellaris-projects` bridge network, which
  is created with inter-container communication disabled: outbound access remains (for the model
  provider later), but projects cannot reach each other. The API reaches them through the
  Docker API (inspect/exec/archive), not over the network.
- **Provisioning.** `POST /projects` inserts a hidden `provisioning` row, creates the
  volume and container, and waits for the container health check. Only then does the
  project become visible (`ready`) and the 201 response is stored for idempotent replay.
  On a Docker failure the row becomes `failed` (hidden), the key is released, and the
  client gets `503 SERVICE_UNAVAILABLE`; retrying with the same key reuses the same
  project ID, volume, and container names.
- **Restart reconciliation.** At startup, before serving: in-progress idempotency keys
  become retryable and interrupted provisionings become `failed`. A background thread
  then ensures each `ready` project (active or archived) has a running container,
  recreating a missing container on its existing volume. A missing volume is logged
  and never replaced with an empty one.
- **Data retention.** Nothing deletes volumes or containers. Archive keeps the container
  running; the project-ending/teardown operation is still undecided.

## Uploads and artifact storage

- **Flow.** `POST /uploads` (idempotent; validates filename label, MIME allowlist → 415, kind/MIME
  compatibility, `size_bytes` ≤ `max_file_bytes` → 413, project quota → 413, optional `sha256`,
  capture consent for browser recordings, `experiment_id` in the project) → `PUT …/content` →
  `POST …/complete` with `{}` (idempotent).
- **Transfer.** The PUT body is streamed from the WSGI input to
  `/data/uploads/<upload_id>.<random>.part` in the API volume (bounded memory; chunked transfer
  encoding accepted; actual bytes are counted and hashed). `Content-Type` must equal the declared
  MIME (415). More bytes than declared → 413 immediately; a different total → 422
  `VALIDATION_FAILED`; declared hash mismatch → 422 `HASH_MISMATCH`. These leave the upload
  `pending` so the PUT can be retried. Success renames the file to `<upload_id>.bin` and marks
  `uploaded`. A repeat PUT with the same hash/size → 204; different bytes → 409
  `UPLOAD_CONTENT_CONFLICT`. Concurrent PUT/complete for one upload → 409 `UPLOAD_IN_PROGRESS`
  (in-process lock; the API runs one Gunicorn process).
- **Completion.** Re-hashes the bytes, validates content (see below), checks the project quota,
  writes the bytes into the project volume, then commits the artifact row, `artifact.created`,
  `upload.updated`, and the idempotent response in one transaction. Content validation failures
  mark the upload `failed` (the stored error is returned on later completes). Each upload reserves
  its artifact ID at creation, so a retry after a crash overwrites the same storage path. A
  completed upload always returns the same artifact, even after the idempotency key expires.
- **Expiry.** `expires_at` = creation + `STELLARIS_UPLOAD_EXPIRY_S` (default 24 h). Expired
  pending/uploaded uploads become `expired` when next touched (410 `UPLOAD_EXPIRED` for PUT/complete)
  and their temporary bytes are deleted; at startup, due uploads are expired and every temporary
  file not belonging to an `uploaded` upload is removed.
- **Content validation** (`api/stellaris_api/media.py`). Accepted uploads: `video/mp4`,
  `video/quicktime`, `video/webm`, `image/png`, `image/jpeg`, `text/plain`, `text/markdown`,
  `text/csv`, `text/x-python`. Video/image: ffprobe is forced to the demuxer implied by the declared
  type (so a PNG declared as MP4 fails), must find a video stream and decode at least one frame;
  width/height (swapped for 90°/270° rotation metadata), duration (container duration, else packet
  timestamps) ≤ `max_video_duration_ms`, `nb_frames` when the container records it, and nominal
  frame rate come from ffprobe. Text: entire file strict UTF-8 without NUL bytes. ffprobe runs as uid
  65534 with a 1 GiB address-space limit, a CPU-time limit, a wall-clock timeout, one decoder thread,
  an empty environment, and the `file` protocol only.
- **Storage.** Ready artifact bytes live only in the owning project's volume at
  `/workspace/data/artifacts/<artifact_id>`, written and read through the Docker archive API with
  fixed paths (no shell, no exec of interpolated commands, works whether the container is running
  or not). Files are root-owned 0444 in a root-owned 0755 directory, so the project runtime user
  can read but not change them. Client filenames are labels only.
- **Downloads.** `GET …/artifacts/{id}/content` streams from the volume with bounded memory,
  single `Range` requests (206/416, `If-Range`), `ETag` = `"<sha256>"`, `Content-Disposition:
  attachment` by default, `?disposition=inline` only for PNG/JPEG/MP4/WebM/QuickTime/plain text/
  Markdown/CSV, `X-Content-Type-Options: nosniff`, and a sandboxing CSP. Full downloads re-verify
  the sha256 and hold back the last chunk, so tampered bytes produce a truncated response.

## Events (SSE)

`GET /api/v1/projects/{id}/events?after=<event_cursor>` streams persisted events strictly after
the cursor, then polls for new ones (0.5 s) and sends `: heartbeat` comments when idle for 15 s.
`Last-Event-ID` takes precedence over `after`; with neither, the stream starts live. Cursors are
opaque and bound to their project (another project's cursor → 400 `INVALID_EVENT_CURSOR`).
Events older than `STELLARIS_EVENT_RETENTION_S` (default 7 days, reported as
`event_retention_seconds`) are purged when a stream opens, always keeping the newest; a cursor
older than the retained history → 410 `EVENT_CURSOR_EXPIRED`. Responses set
`Cache-Control: no-store, no-transform` and `X-Accel-Buffering: no`. Each open stream occupies one
of the 32 Gunicorn threads.

## Helper interfaces for later slices

All raise `ApiError` for contract errors. "In a transaction" means inside
`with db.transaction(conn):` on a connection owned by the calling thread (`db.connect(path)`).

```python
# stellaris_api/research.py — call in a transaction
publish_source(conn, project_id, *, title, url, provider="manual", authors=(), external_id=None,
               published_at=None, doi=None, abstract=None, retrieval_status="metadata_only",
               retrieved_at=None, document_artifact_id=None, allow_archived=False) -> dict  # Source
publish_claim(conn, project_id, *, run_id, kind, text, measurement_ids=(), citations=(),
              evidence=(), assumptions=(), limitations=(), allow_archived=True) -> dict  # Claim
#   measurement_ids must be empty until a measurements table exists; run_id is not yet checked.

# stellaris_api/experiments.py — call in a transaction
create_experiment(conn, project_id, fields: dict) -> dict                       # Experiment, revision 1
update_experiment(conn, project_id, experiment_id, changes: dict, *, expected_revision: int) -> dict

# stellaris_api/artifacts.py
stage_artifact(conn, runtime, config, project_id, *, local_path, filename, mime_type, kind, origin,
               experiment_id=None, run_id=None, parent_artifact_ids=()) -> dict
#   validates + stores bytes in the project volume; NOT visible until committed (no transaction)
commit_artifact(conn, staged: dict) -> dict          # call in a transaction; emits artifact.created
publish_artifact(runtime, config, project_id, *, local_path, filename, mime_type, kind, origin,
                 experiment_id=None, run_id=None, parent_artifact_ids=()) -> dict  # own connection
publish_text_artifact(runtime, config, project_id, *, text, filename, mime_type="text/markdown",
                      kind="report", origin="generated", experiment_id=None, run_id=None,
                      parent_artifact_ids=()) -> dict

# stellaris_api/events.py — call in a transaction with the resource change
record_event(conn, project_id, event_type, payload: dict, run_id=None) -> int

# stellaris_api/runtime.py (ProjectRuntime) — Docker archive API, fixed paths
store_artifact(project_id, artifact_id, local_path, tmp_dir) -> None
open_artifact(project_id, artifact_id) -> (size, reader, close)
```

`runtime` is `app.extensions["stellaris_runtime"]` and `config` is `app.config["STELLARIS"]`.
Generated artifacts additionally allow `application/json` (dataset/environment/document/log) and
kinds `chart`, `report`, `log`, `environment` for the matching types in `media.TYPES`.

## Known gaps (slice 2)

- The project runtime user owns `/workspace/data`, so it could rename the root-owned `artifacts`
  directory and plant different files. Full downloads detect changed bytes by hash; range requests
  only check the size.
- ffprobe parses untrusted media inside the trusted API container (non-root, rlimited); a throwaway
  container would isolate it better.
- JPEG EXIF orientation is not applied to reported image dimensions (ffprobe 5.1 does not expose it).
- Project quota is checked at upload creation and completion; concurrent completions can briefly
  exceed it by at most one file.
- `video/webm` is accepted via the Matroska demuxer, so a Matroska (`.mkv`) file declared as WebM
  also passes.
- An orphaned file can remain in the volume if the API crashes after storing bytes but before the
  artifact row commits (uploads reuse their reserved path; other publishers do not).
- Expired SSE cursors (410) are implemented but not exercised by the integration script.

## Manual cleanup (destructive, local dev only)

These delete project data permanently. Look at what they match before running them.

```bash
docker ps -a --filter label=stellaris.managed=true
docker volume ls --filter label=stellaris.managed=true
# docker rm -f $(docker ps -aq --filter label=stellaris.managed=true)
# docker volume rm $(docker volume ls -q --filter label=stellaris.managed=true)
# docker compose down -v      # also removes the SQLite volume stellaris-api-data
```
