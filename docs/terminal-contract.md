# Interactive terminal contract

Status: implemented and locally Docker/API verified; frontend integration is separate. The terminal is an
optional, user-started shell for inspecting and manipulating project-local scratch files.
It is not the research agent workspace, a scientific execution environment, or an API
authorization boundary.

## Isolation and lifecycle

The trusted primary backend creates one non-root `stellaris-terminal` container
per active session. Each project has a dedicated named terminal volume, distinct from
project research scratch and published artifacts. The image starts `/bin/bash
--noprofile --norc` on a real Docker TTY. No provider credentials, host mounts, Docker
socket, or network are passed. The root filesystem is read-only; `/tmp`, `/home/terminal`,
and `/workspace` are writable. The runtime drops all capabilities, enables no-new-privileges,
and limits CPU, memory, processes, input, output, and duration.

At most one session is active per project. Closing a session or restarting the API removes
its container but preserves its named terminal volume. Startup recovery marks previously
active sessions lost/closed and removes only containers with both Stellaris managed and
terminal role labels. A missing existing volume is reported as unavailable; it is never
silently replaced with an empty volume. Archived projects may close or read old sessions,
but cannot start or send input/resize to one.

## HTTP API

All routes are under `/api/v1/projects/{project_id}` and project scoped. Cross-project
session IDs return 404. Mutating POSTs require an `Idempotency-Key`. `starting` means only
that the request was accepted; it does not mean a command ran.

- `POST /terminals` body `{ "rows": 24, "cols": 80 }` starts or replays a session; returns
  202 and `Session`.
- `GET /terminals?limit=50&cursor=...` returns a project page of sessions.
- `GET /terminals/{terminal_id}` returns `Session`.
- `PUT /terminals/{terminal_id}/input/{sequence}` body
  `{ "data_base64": "..." }`. Sequences start at 1 and must be strictly contiguous.
  A receipt and body hash are committed before bytes are sent. Same-sequence/same-body
  replay never sends bytes twice; changed body returns 409; a gap returns 409 with the
  expected sequence. Ambiguous receipts after a crash are never resent.
- `PUT /terminals/{terminal_id}/size` body `{ "rows": 24, "cols": 80 }` is idempotent.
- `POST /terminals/{terminal_id}/close` body `{}` closes idempotently, including archived
  projects.
- `GET /terminals/{terminal_id}/output?after_sequence=0&limit=50&cursor=...` returns a
  project/session/filter-bound `Page` of persisted ordered chunks. `GET /terminals/{terminal_id}/transcript` downloads concatenated raw bytes
  as `application/octet-stream`.

`Session` fields: `id` (`trm_...`), `project_id`, `status` (`starting`, `running`, `closing`,
`closed`, `failed`), `rows`, `cols`, `created_at`, `finished_at`, safe nullable `error`
`{code,message}`, `output_bytes`, `last_output_sequence`, `last_input_sequence`, and nullable
`transcript_artifact_id` (currently null). Output chunks are at most 4096 bytes and at most
2 MiB are retained per session; output is stopped with an explicit `output_limit` reason when
the cap is reached. Sessions end after one hour with `time_limit`. Input is at most 16 KiB
per request and at most 10,000 input receipts are retained.

Committed session and output changes emit project SSE events `terminal.updated` with
`{ "terminal": Session }` and `terminal.output` with
`{ "terminal_id": "trm_...", "sequence": 1, "data_base64": "..." }`.
Output sequence numbers and bytes are persisted in the main SQLite database and replayable
through the output route. Terminal transcripts are not artifacts until a separate explicit
publish operation is designed and implemented.

## Backend integration hooks

The terminal module exports `init_schema(conn)` for the existing main database,
`TerminalManager(config, runtime)`, and blueprint factory `create_blueprint(manager)`.
Application startup calls `manager.start()` (which cleans stale labelled containers and
marks old active rows lost), then `manager.recover()`; shutdown calls `manager.close_all()`.
The capability response reports `manager.available()` and configured limits. `runtime` is
the trusted project runtime and supplies `client()`; terminal-specific settings are loaded
only from `STELLARIS_TERMINAL_*` names. Root owns all integration points and must register
the blueprint under the existing error and request-ID handlers.

Output uses the common `Page<T>` shape with `items` and opaque `next_cursor`. Cursors retain
`after_sequence` and bind the terminal and project; conflicting explicit filters return 400.
Session listings also paginate with opaque project-bound cursors. Rows range from 2–200 and
columns from 2–500. Terminal files persist only in the separate terminal workspace; no research
scratch or evidence filesystem is mounted. Transcript artifact publishing is not implemented.
