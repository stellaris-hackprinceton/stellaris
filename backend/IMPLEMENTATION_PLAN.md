# Stellaris backend implementation plan

Goal: the bouncing-ball research → experiment → measurement → Markdown-report workflow
(Contracts.md §11) end to end, before any other modality or integration.

## Implementation status

Status words: **implemented** = code exists; **verified** = a check was observed passing.
Do not mark a slice verified until its script has actually been run against rebuilt images.

| Slice | Status |
| --- | --- |
| 1 — foundation | Implemented. `scripts/smoke_test.py` written; its run was in progress at the time slice 2 was written (record the result here). |
| 2 — resources, uploads/artifacts, SSE | Implemented, **not yet run**. Verify with `scripts/integration_test.py` after rebuilding both images. |
| 3 — Deep Agents runtime | Not started. |
| 4 — chat and agent runs | Not started. |
| 5 — isolated analysis workers | Not started. |
| 6 — reports and end-to-end demo | Not started. |

## Slice 1 — foundation

- Flask API, contract error envelope, `X-Request-ID`, host/origin guards, no auth.
- SQLite: `projects`, `idempotency_keys`, `events`.
- `GET /health`, `/session` (dev compatibility), `/capabilities`.
- Projects: create/list/get/patch/workspace, ETags, `If-Match`, idempotent POST, archive/restore.
- Dynamic per-project container + named volume, created on project creation; restart reconciliation.

## Slice 2 — persistent resources, uploads/artifacts, events (this slice)

Implemented:

- SQLite tables `sources`, `experiments`, `claims`, `uploads`, `artifacts` (public JSON in `doc`;
  indexed columns for filters/ordering). Workspace counts are real (`runs` stays 0).
- Sources: manual `POST` (idempotent), list (`provider` filter), get. Immutable snapshots.
- Experiments: `POST` (idempotent, ETag, Location), list, get (ETag), `PATCH` (`If-Match`, 428/412,
  arrays replace, no-op keeps revision). Every save checks referenced artifacts are ready and in the
  project (`422 INVALID_REFERENCE`), and reference-length calibration: artifact is an attached video
  or image, `frame_index` 0 for images and below a known video frame count, distinct points inside
  the frame (dimensions from ffprobe), positive length, nonnegative or null uncertainty.
- Claims: list (`run_id` filter) and get. No public writes; `publish_claim()` for later runs.
- Uploads: create → `PUT` content → complete, as specified in Contracts.md §6 (details in README).
- Artifacts: list (`kind`, `experiment_id`, `run_id` filters), get, content with single byte ranges
  (206/416, `If-Range`), sha256 ETag, attachment by default, inline allowlist, `nosniff`, sandbox CSP.
- `GET /projects/{id}/events` SSE (ordered replay, project-bound cursors, `Last-Event-ID` precedence,
  heartbeat, retention/expiry). All resource writes emit their events in the same transaction.
- Strict request validation: unknown fields, finite numbers (NaN/Infinity/overflow → 400 `MALFORMED_JSON`).
- Capabilities: upload MIME types and limits and `event_retention_seconds` are now real values.
  All feature flags stay `false` (`experiment_design` turns on when agent tools create experiments).

Contract discrepancies to confirm with the user (codes not listed in Contracts.md §9):

- `409 UPLOAD_IN_PROGRESS` and `409 UPLOAD_CONTENT_CONFLICT` are in §6 but not §9's list (used as specified).
- `409 UPLOAD_FAILED`: `PUT` content to an upload that failed validation (contract is silent).
- `416 RANGE_NOT_SATISFIABLE`: JSON error code for unsatisfiable ranges (contract only says 416).
- `409 ARTIFACT_NOT_READY`: reused for completing an upload whose content was never transferred.
- Size/hash mismatches are reported by the content `PUT` (422 `VALIDATION_FAILED` / `HASH_MISMATCH`)
  and leave the upload `pending` for a retry; media validation at completion marks it `failed`.
- `GET /events` without `after`/`Last-Event-ID` starts live from the latest event (contract silent).

## Slice 3 — events consumers and Deep Agents runtime

- Verify the current LangChain Deep Agents API, pin it, and install it in the project
  runtime image. The agent uses `/workspace/scratch` as its filesystem backend.
- Backend ↔ runtime protocol: the API invokes the agent per run through `docker exec`
  (or an internal HTTP endpoint reachable only from the API — decide and document).
  Agent tools call back into backend-controlled operations; agents never write SQLite.
  Tools map onto the slice-2 helpers (`publish_source`, `create_experiment`,
  `update_experiment`, `publish_claim`, `publish_artifact`).
- Pass `OPENAI_API_KEY`/`OPENAI_MODEL` to project containers only as needed; redact in logs.

## Slice 4 — chat and agent runs

- `messages` and `runs` tables; `POST /messages` atomically creates user message,
  assistant placeholder, queued agent run (202). Run state machine per §7.
- In-process run queue in the API (single worker); `WORKER_LOST` on restart.
- Delta persistence + `message.delta`/`message.updated`/`run.updated` events.
- `experiment_design: true` once agent tools can create Experiments.
- Literature provider: blocked on user choice (arXiv/OpenAlex/Semantic Scholar) and
  credentials. Until decided, only manual sources; never invent retrieved sources.

## Slice 5 — isolated analysis workers

- `bouncing_ball_v1`: OpenCV pipeline in a separate worker image.
- Per run: temporary container, `network_disabled`, read-only inputs copied in via archive,
  writable `/output`, CPU/memory/wall-time limits, no socket, removed after collection.
- Validate `/output/result.json` (§10), publish measurements/claims/artifacts with
  `stage_artifact()` + `commit_artifact()` + `publish_claim()` in one transaction, provenance
  manifest (image digest, versions, calibration conversion), logs as artifact.
- Add `measurements` table; `publish_claim()` then accepts measurement IDs.
- `python_analysis_v1` after the bouncing-ball pipeline works. Enable `video_analysis` then.

## Slice 6 — reports and end-to-end demo

- Report run → immutable Markdown artifact via `publish_text_artifact()`, built only from
  committed evidence runs, including failures and missing measurements. Charts as image artifacts.
- End-to-end smoke test with a real recorded video (never synthetic data labelled observed).

## Open decisions

- What ends a project's duration (and therefore container teardown); data retention on end.
- Literature provider(s) and credentials.
- Authentication provider (contract §3 deferred) before any non-localhost deployment.
- Cleanup policy for hidden `failed` provisioning rows and their volumes.
- Whether ffprobe should move from the API container into a throwaway container (stronger isolation).
- Contract error codes listed under slice 2.
