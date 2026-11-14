# Stellaris file workspace contract

Contract version: **1.1.0-draft (additive to `/api/v1`)**
Status: **Proposed. No part of this document is implemented yet.** Progress is tracked in
[backend/file-workspace-plan.md](backend/file-workspace-plan.md).
Prepared: **November 14, 2026**
Extends: [frontend-backend-contract.md](frontend-backend-contract.md). Its sections 3 (common
rules, development mode without authentication), 6 (artifact content), 8 (events), and 9
(errors) apply unless this document states otherwise.

## 1. Purpose and supersession

Users asked for one free-form workspace of files instead of fixed sections and tables. This
contract adds that interface:

- Every artifact and every existing scientific record appears as a **file** in one list.
- Former fixed categories such as research, hypotheses, results, artifacts, and agent logs
  become **default tags**. Users can add their own tags.
- Users can write mutable Markdown or plain-text **notes** with retained revisions.
- Users can group files into **collections** and connect them with explicit directed
  **relations**. These relations can later feed an Obsidian-style graph.

**Supersession.** For new workspace and navigation UI, use `/files`, `/tags`,
`/collections`, and `/relations` instead of rigid per-category screens. The legacy routes
remain available, unchanged, and authoritative for scientific records and commands. These
include `/sources`, `/claims`, `/experiments`, `/artifacts`, `/uploads`, `/runs`, and
`/messages`. Use the legacy routes to create sources, edit experiments, upload media, and
start runs. The file workspace organizes and exposes those records. It does not replace
their validation or provenance rules.

**Explicitly out of scope:** folders and folder CRUD, full-text or semantic search,
embeddings, inferred or similarity-based links, graph rendering or layout endpoints, agent
access to notes or tags, and file hard deletion.

## 2. Concepts and invariants

| Concept | Meaning |
|---|---|
| File | A catalog entry with a name, MIME type, bytes, tags, and an origin. |
| `file_kind: "artifact"` | An existing immutable `Artifact`. Its bytes are the artifact's bytes. The catalog never copies them. |
| `file_kind: "record"` | A read-only structured rendering of a legacy record. These include a Source, Claim, Experiment, terminal Run, or a terminal analysis run's measurements. The legacy record remains the source of truth. |
| `file_kind: "note"` | User-authored mutable text. It is never scientific evidence. |
| Tag | An organizational label. A tag is never a scientific classification, provenance statement, or evidence. |
| Collection | A user-named set of files with explicit membership, or a saved filter whose membership is evaluated on read. |
| Relation | An explicit directed edge between two files. A relation is either user-authored or a system relation copied from recorded provenance. |

Invariants:

1. **Immutable originals.** Artifact bytes and legacy record content cannot change through
   this API. Only notes have editable content.
2. **No duplicated evidence.** Each legacy record or artifact has exactly one file, with a
   deterministic ID derived from `(project_id, origin.type, origin.id)`. A backfill or
   re-projection reuses that ID. A record file adds no evidence and does not alter its
   original's `created_at`.
3. **Tags are organizational, not scientific.** A user-applied `hypotheses` tag on a note does
   not make that note a hypothesis `Claim`. Scientific meaning comes only from `file_kind`,
   `origin`, and `scientific_origin`, and from the linked legacy record.
4. **Notes are not evidence.** Notes cannot be cited by claims, used as run inputs, or included
   in reports as evidence. Freezing a note into an immutable artifact is future work.
5. **Agent scratch remains private.** Nothing under the agent's scratch space is projected.
6. **Project scope everywhere.** Every file, tag, collection, and relation belongs to one
   project. A referenced ID outside the route's project returns `422 INVALID_REFERENCE` in
   request bodies and `404 RESOURCE_NOT_FOUND` in route paths. The response does not
   disclose whether the resource exists elsewhere. Project IDs are not an authorization
   boundary. No authentication is added.
7. **Archived projects** are readable. Every mutation in this document returns
   `409 PROJECT_ARCHIVED`. Projection of runs that finish after archiving continues.

## 3. Capability

`GET /capabilities` gains an optional `features.workspace_files?: boolean`. Treat a missing
value as `false`. When it is `false`, the routes below may return `404` and the frontend
uses the legacy screens.

## 4. Types

Common types such as `ID`, `Timestamp`, `Page<T>`, and the error envelope come from the
base contract.

```ts
type FileKind = "artifact" | "record" | "note"
type FileOriginType =
  | "artifact"          // origin.id is an Artifact ID
  | "source"            // Source ID
  | "claim"             // Claim ID
  | "experiment"        // Experiment ID
  | "run"               // terminal Run ID
  | "run_measurements"  // Run ID of a terminal analysis run with >= 1 measurement

type ScientificOrigin = "observed" | "derived" | "simulated" | "generated" | "reference"

type FileTag = { slug: string, assigned_by: "system" | "user" }

type WorkspaceFile = {
  id: ID,                         // "fil_" + 32 hex; opaque
  project_id: ID,
  name: string,                   // display label, never a path
  file_kind: FileKind,
  origin: { type: FileOriginType, id: ID, revision: number | null } | null,  // null only for notes
  scientific_origin: ScientificOrigin | null,
  mime_type: string,
  size_bytes: number,
  content_sha256: string,         // SHA-256 of the bytes served by GET .../content (current revision)
  editable: { name: boolean, content: boolean, tags: true },
  status: "active" | "trashed",   // always "active" for artifact/record files
  tags: FileTag[],                // sorted by slug
  collection_ids: ID[],           // sorted explicit memberships only; saved filters are evaluated separately
  content_revision: number | null,// notes: current content revision (1-based); others null
  revision: number,               // catalog metadata revision; ETag
  created_at: Timestamp,          // legacy created_at for projected files
  updated_at: Timestamp
}

type NoteRevision = {
  file_id: ID,
  content_revision: number,
  name: string,                   // name at that revision
  mime_type: "text/markdown" | "text/plain",
  size_bytes: number,
  content_sha256: string,
  created_at: Timestamp
}

type Tag = {
  slug: string,                   // identity; immutable
  label: string,
  color: string | null,           // "#rrggbb" lowercase or null
  system: boolean,                // default tag; cannot be deleted
  file_count: number,             // active files currently carrying the tag
  revision: number,
  created_at: Timestamp,
  updated_at: Timestamp
}

type Collection = {
  id: ID,                         // "col_" + 32 hex
  project_id: ID,
  name: string,
  description: string,
  filter: FileFilter | null,      // null: explicit members; otherwise a saved dynamic filter
  file_count: number,
  revision: number,               // covers name/description/filter, not explicit membership
  created_at: Timestamp,
  updated_at: Timestamp
}

type FileFilter = {
  tags?: string[],                // AND; at most 10
  file_kind?: FileKind,
  origin_type?: FileOriginType,
  status?: "active" | "trashed" | "all", // default active
  q?: string                     // name substring, 1–100 characters
}

type RelationType = string        // slug, see section 9
type Relation = {
  id: ID,                         // "rel_" + 32 hex
  project_id: ID,
  from_file_id: ID,
  to_file_id: ID,
  type: RelationType,
  note: string | null,
  created_by: "user" | "system",
  created_at: Timestamp
}

type CatalogStatus = {
  schema_version: number,
  workspace_files: boolean,
  last_synced_at: Timestamp | null,
  projected: {                    // counts of projected files by origin type
    artifact: number, source: number, claim: number, experiment: number,
    run: number, run_measurements: number
  },
  notes: { count: number, retained_bytes: number, max_bytes: number },
  last_sync_error: { code: string, message: string } | null
}
```

`scientific_origin` uses these values:

| File | Value |
|---|---|
| Artifact file | The artifact's `origin`. |
| Source record | `"reference"`. |
| Measurements file | `"simulated"` if any row is simulated. Otherwise `"derived"` if any row is derived. Otherwise `"observed"`. |
| Claim, experiment, or run record | `null`. Read the record's own fields. |
| Note | `null`. |

Simulated labels are never removed.

## 5. Projection and backfill

The backend projects legacy records into the catalog automatically. There is no backfill
command and no client action. The first catalog request for a project performs the
backfill. Each later catalog request checks for and applies any newer legacy changes before
it responds.

| Legacy record | File becomes visible | `name` | `mime_type` | System tags |
|---|---|---|---|---|
| Artifact | When committed | `artifact.filename` | the artifact's type | `artifacts`, plus a kind-based tag from the list below |
| Source | When created | `<title>.source.json` | `application/json` | `research` |
| Claim | When created | `claim-<kind>-<id8>.json` | `application/json` | `hypotheses` for `hypothesis`; otherwise `results` |
| Experiment | When created; content follows each revision | `<title>.experiment.json` | `application/json` | `experiments` |
| Run | When terminal (`succeeded`, `failed`, or `cancelled`) | `run-<kind>-<id8>.json` | `application/json` | `results` |
| Measurements of a terminal analysis run with at least one measurement | When the run becomes terminal | `measurements-<run id8>.csv` | `text/csv` | `results` |

Artifacts also receive a kind-based tag for every existing category: `document` → `documents`,
`dataset` → `datasets`, `image` → `images`, `video` → `videos`, `audio` → `audio`,
`code` → `code`, `chart` → `charts`. Additionally:

- `report` → `reports`
- `log` from an agent run → `agent-logs`
- `log` from another run → `run-logs`
- `environment` → `provenance`

Chat messages, uploads in progress, and agent scratch files are not projected.

Naming rules:

- `<id8>` is the last 8 hexadecimal characters of the legacy ID.
- In titles, path separators, control characters, and surrounding spaces are replaced or
  trimmed.
- Titles are truncated to 120 characters.
- Names are labels and are not unique.

Content rules:

- **Record JSON** is UTF-8, uses 2-space indentation, has sorted keys, and ends with a
  newline. It uses this exact envelope:

  ```json
  {
    "schema": "stellaris.record.v1",
    "record_type": "source",
    "project_id": "prj_…",
    "id": "src_…",
    "revision": null,
    "api_path": "/api/v1/projects/prj_…/sources/src_…",
    "data": { "…": "the public legacy resource, verbatim" }
  }
  ```

- The `data` field depends on the record type:
  - Runs: `data` is `{ "run": Run, "results": RunResults }`.
  - Experiments: `revision` equals `experiment.revision`.
  - Other records: `revision` is `null`.
- **Measurements CSV** uses RFC 4180 with a header row. Rows are in `(created_at, id)`
  order. The columns are:
  `id,series,quantity,value,unit,time_s,uncertainty_absolute,uncertainty_method,status,calibration_mode,data_origin,assumptions_json,evidence_json`.
  A `null` value is an empty field. Values are never fabricated. Each row's `data_origin`
  is preserved.
- Rendering is deterministic for a given legacy state and a given renderer version. When an
  experiment is revised, its file's `content_sha256`, `size_bytes`, `origin.revision`,
  `revision`, and `updated_at` change. Experiment history is not stored in the catalog.
  Reproducible plan state remains in each run's accepted snapshot.

Consistency:

- Catalog reads reflect every legacy change committed before the request started.
- Projection is idempotent. Repeating it never creates a second file for the same origin.

## 6. Default tags

System tags exist in every catalog:

`research`, `hypotheses`, `experiments`, `results`, `artifacts`, `reports`, `agent-logs`,
`run-logs`, `provenance`, `notes`, `documents`, `datasets`, `images`, `videos`, `audio`, `code`, `charts`.

- A system tag can be renamed through `label` and recolored. It cannot be deleted. Its slug
  never changes.
- System assignments are made by projection (section 5). New notes always receive `notes`.
  They cannot be removed by a client. Explicit bulk removal returns `422`; PATCH only replaces user assignments.
- Users may assign any tag, including a system tag, through user assignments. For example,
  a user may tag a note `hypotheses`. A user assignment does not change the file's
  scientific meaning. If a system assignment already exists for that slug, the user
  assignment is a no-op.

## 7. Routes

All routes are relative to `/api/v1/projects/{project_id}`. A project that is not visible
returns `404 RESOURCE_NOT_FOUND`.

### Catalog

- `GET /catalog` → `200 CatalogStatus`. If the catalog has just been created, this request
  runs the backfill. A failed sync still returns `200` with `last_sync_error`. A catalog
  that cannot be opened returns `503 SERVICE_UNAVAILABLE` with `Retry-After`.
  Other catalog routes return `503` on sync failure rather than silently serving stale projections.

### Files

- `GET /files` → `200 Page<WorkspaceFile>`. Query parameters are listed in section 8.
- `GET /files/{file_id}` → `200 WorkspaceFile` and `ETag: "<revision>"`.
- `POST /files` creates a note → `201 WorkspaceFile`, `ETag`, and `Location`. It requires
  `Idempotency-Key`.

  ```ts
  type CreateNote = {
    name: string,
    content: string,
    mime_type?: "text/markdown" | "text/plain",  // default "text/markdown"
    tags?: string[]                              // user tag slugs; created if absent
  }
  ```

  The new note has `content_revision: 1`, `revision: 1`, `status: "active"`, and the system
  tag `notes`.

- `PATCH /files/{file_id}` requires `If-Match` → `200 WorkspaceFile` and a new `ETag`.
  - The body must contain at least one of: `name` and `content` (notes only), `status`
    (notes only, `"active"` or `"trashed"`), or `tags` (any file).
  - `tags` replaces user-assigned tags. System assignments remain even when omitted;
    listing a system-assigned slug is a no-op. Bulk tagging explicitly removing a system assignment returns `422`.
  - `content` whose bytes differ from the current revision creates a new
    `content_revision`. Identical content creates no revision. A `name` change alone
    creates no content revision.
  - Changing `name`, `content`, or `status` on an artifact or record file returns
    `409 FILE_READ_ONLY`.
  - A PATCH whose values equal the current values returns the unchanged revision.

- `POST /files/tagging` applies tags to many files → `200 { files: WorkspaceFile[] }`, in
  request order. It requires `Idempotency-Key`. No `If-Match` is needed because the
  operations are set operations.

  ```ts
  type TaggingRequest = { file_ids: ID[], add?: string[], remove?: string[] }
  ```

  - Slugs in `add` are created as user tags if they do not exist.
  - `remove` affects only user assignments. Removing a system assignment returns `422`.
  - Only files whose tags change get a new `revision`.

- `GET /files/{file_id}/content` streams the file's bytes.
  - **Artifact files** behave exactly like `GET /artifacts/{artifact_id}/content`: Range
    requests and `206`/`416`, `ETag` equal to the SHA-256, `disposition` handling,
    `nosniff`, sandbox CSP, and integrity truncation.
  - **Record files** are rendered on request and returned with `200`. `ETag` is the
    SHA-256 of the response bytes. Range headers are ignored. If the response SHA-256
    differs from the file's `content_sha256`, the newest legacy state was served and the
    metadata catches up on the next request.
  - **Notes** return the current revision. `?revision=N` selects a retained
    `content_revision`. An unknown revision returns `404`. `ETag` is the revision's SHA-256.
  - `?revision` on a non-note returns `400 INVALID_QUERY`.
  - The default is `Content-Disposition: attachment`. `?disposition=inline` is allowed for
    the base contract's inline types: images, video, `text/plain`, `text/markdown`, and
    `text/csv`. For other types it returns `400 INVALID_QUERY`, exactly as for artifacts.
- `GET /files/{file_id}/revisions` → `200 Page<NoteRevision>`, in ascending
  `content_revision` order. A non-note returns `409 FILE_KIND_UNSUPPORTED`.

### Tags

- `GET /tags` → `200 Page<Tag>` sorted ascending by `slug`. Optional `system=true|false`.
- `POST /tags` `{ slug, label?, color? }` → `201 Tag`, `ETag`, and `Location`. It requires
  `Idempotency-Key`. `label` defaults to `slug`. An existing slug returns `409 TAG_EXISTS`.
- `GET /tags/{slug}` → `200 Tag` and `ETag`.
- `PATCH /tags/{slug}` `{ label?, color? }` requires `If-Match` → `200 Tag`.
- `DELETE /tags/{slug}` requires `If-Match` → `204`. This removes all user assignments of the
  tag. A system tag returns `409 TAG_PROTECTED`. Every affected file gets a new revision
  and a file change event (a bulk invalidation is allowed).

### Collections

- `GET /collections` → `200 Page<Collection>`, ascending `(created_at, id)`.
- `POST /collections` `{ name, description?, filter? }` → `201 Collection`, `ETag`, and `Location`. It
  requires `Idempotency-Key`.
- `GET /collections/{collection_id}` → `200 Collection` and `ETag`.
- `PATCH /collections/{collection_id}` `{ name?, description?, filter? }` requires `If-Match` →
  `200 Collection`.
- `DELETE /collections/{collection_id}` requires `If-Match` → `204`. This removes the
  collection and its memberships only. Files are untouched.
- `POST /collections/{collection_id}/files` `{ file_ids: ID[] }` →
  `200 { collection: Collection, added_file_ids: ID[] }`. It requires `Idempotency-Key`.
  A saved-filter collection returns `409 COLLECTION_READ_ONLY`. It adds the files to an explicit collection. Files that are already members are ignored and are
  not listed in `added_file_ids`. The collection `revision` does not change.
- `DELETE /collections/{collection_id}/files/{file_id}` → `204`. The response is the same
  whether or not the file was a member. An unknown file or collection returns `404`.
  A saved-filter collection returns `409 COLLECTION_READ_ONLY`.
- List the members of a collection with `GET /files?collection_id=…`.

Membership semantics:

- Membership is a set. A file may belong to any number of collections.
- Trashed notes keep their memberships. Default listings hide trashed notes (section 8).
- `filter: null` (default) uses explicit membership. A non-null `filter` evaluates the
  documented file filters dynamically. No recursive collection filters are allowed.
- `FileFilter.tags` maps to repeatable `tag` query parameters. Its own omitted `status`
  defaults to `active`. On a saved collection request, omitted query filters add no extra
  constraint; explicit query filters intersect the saved filter. Status is a set:
  intersecting `all` with `trashed` yields `trashed`, while `active` with `trashed` is empty.
- `file_count` counts the files returned by `/files?collection_id=…` with no extra filters
  or pagination. Explicit collection counts exclude trashed notes; saved collections use
  their saved status. Counts are derived and are not covered by metadata ETags.
- Explicit membership changes bump each affected file's revision and emit file changes;
  the collection metadata revision remains unchanged. A file's `collection_ids` lists only
  explicit memberships, never dynamic saved-filter membership.
- PATCH may change a saved filter, or switch modes only if the explicit membership is empty;
  otherwise return `409 COLLECTION_NOT_EMPTY`. No membership is silently discarded.
  Omitted `filter` leaves it unchanged; explicit `filter: null` selects explicit mode.

### Relations

- `GET /relations` → `200 Page<Relation>`, ascending `(created_at, id)`. Filters:
  - `file_id`: optional.
  - `direction`: `out`, `in`, or `both`. Default `both`. Requires `file_id`.
  - `type`: optional.
  - `created_by`: `user` or `system`. Optional.
- `POST /relations` `{ from_file_id, to_file_id, type?, note? }` → `201 Relation`. It
  requires `Idempotency-Key`. `type` defaults to `"related"`. If the same
  `(from_file_id, to_file_id, type)` relation already exists, the response is
  `200` with the existing relation. That relation's `note` is unchanged.
- `DELETE /relations/{relation_id}` → `204`. A system relation returns
  `409 RELATION_PROTECTED`. An unknown ID returns `404`. A client that retries a successful
  DELETE should treat `404` as done.

No graph endpoint exists in this version. A graph view uses `GET /files` for nodes and
`GET /relations` for edges, filtered by `file_id` or by the files of a collection or tag.
The backend never invents, infers, or ranks links.

## 8. Listing, filter, sort, and cursor semantics

`GET /files` accepts:

| Parameter | Meaning |
|---|---|
| `tag` | Repeatable, up to 10. A file must carry **all** listed slugs (AND). System and user assignments both match. An unknown slug matches nothing. It is not an error. |
| `file_kind` | `artifact`, `record`, or `note`. |
| `origin_type` | One of `FileOriginType`. |
| `collection_id` | Members of that collection. An unknown collection returns `404`. |
| `status` | `active` (default), `trashed`, or `all`. |
| `q` | 1–100 characters. Case-insensitive substring match on `name` only. `%` and `_` are literal. It does not search content. |
| `sort` | `created_at` (default), `updated_at`, or `name`. Name sort uses Unicode case-folded names, then `id`. |
| `order` | `asc` (default) or `desc`. |
| `limit`, `cursor` | As in the base contract: 1–100, default 50. |

- Pages are ordered by `(sort key, id)` in the requested order.
- A cursor is opaque and stores the project, route, sort, order, and every filter.
- A request that supplies a cursor together with different filters returns
  `400 INVALID_QUERY`. A malformed cursor or a cursor from another route or project returns
  `400 INVALID_CURSOR`.
- With `sort=updated_at`, a file may move between pages if it changes during paging, as
  project listings already do.
- Other list routes accept only the filters listed for them. Unknown query parameters are
  ignored, as on existing routes. Unsupported values return `400 INVALID_QUERY`.

## 9. Validation limits

| Field | Rule |
|---|---|
| File/note `name` | 1–255 characters. No `/`, `\`, control characters, or surrounding spaces. Not `.` or `..`. These are the same rules as upload filenames. |
| Note `content` | Strict UTF-8 without NUL. At most 524,288 UTF-8 bytes (512 KiB) per revision. The whole JSON body must also fit the existing 1 MiB request limit, otherwise `413`. |
| Retained note bytes per project | At most `notes.max_bytes`, default 64 MiB, summed over all revisions. When exceeded, the response is `413 PROJECT_QUOTA_EXCEEDED`. This budget is separate from the artifact quota. |
| Tag `slug` | `^[a-z0-9][a-z0-9-]{0,47}$`. |
| Tag `label` | 1–64 characters, trimmed. |
| Tag `color` | `^#[0-9a-f]{6}$` or `null`. |
| Tags | At most 32 user tags per file and 500 tags per project. Otherwise `422`. |
| `TaggingRequest` | `file_ids`: 1–100 unique IDs. `add` and `remove`: 0–32 slugs each. The two lists must not overlap, and at least one must be non-empty. |
| Collection `name` | 1–120 characters, trimmed. |
| Collection `description` | At most 2,000 characters. Default `""`. |
| Collections | At most 200 per project and 10,000 files per collection. Membership requests take 1–100 `file_ids`. |
| Relation `type` | Tag slug pattern. The reserved system types `derived_from`, `produced_by`, `cites`, and `uses_evidence` are rejected with `422`. |
| Relation `note` | At most 1,000 characters, or `null`. |
| Relations | `from_file_id` must differ from `to_file_id`. At most 20,000 per project. |

Request bodies reject unknown fields with `422 VALIDATION_FAILED`. JSON Pointer paths
identify each failing field.

## 10. Relation direction and system relations

A relation reads as **from → to**: "`from_file_id` *type* `to_file_id`". For example,
`report.md derived_from measurements.csv`. Direction is never reversed or inferred.

The backend creates **system relations** only from recorded provenance. They are created
during projection, are read-only, and have deterministic IDs.

| Type | From | To | Recorded source |
|---|---|---|---|
| `derived_from` | artifact file | artifact file | `Artifact.parent_artifact_ids` |
| `produced_by` | artifact file | run record file | `Artifact.run_id`. Created once the run is terminal. |
| `produced_by` | measurements file | run record file | The measurements' run. |
| `cites` | claim record file | source record file | `Claim.citations[].source_id` |
| `uses_evidence` | claim record file | artifact file or measurements file | `Claim.evidence[].artifact_id` or `Claim.measurement_ids` (through their run's measurements file) |

User relations may use any other slug, such as `related`, `references`, `follows-up`,
`questions`, or `todo`. They express user organization, not scientific support.

## 11. Concurrency, retries, and recovery

- **ETags.** Files, tags, and collections return `ETag: "<revision>"` from GET, POST, and
  PATCH. PATCH and DELETE of files, tags, and collection metadata require `If-Match`;
  relation and membership deletion are set operations and do not use ETags. A missing `If-Match` returns
  `428 PRECONDITION_REQUIRED`. A stale value returns `412 REVISION_CONFLICT` with
  `details.current_revision`.
- **What changes a file's `revision`.** The `revision` of artifact and record files also
  increases when projection changes them, for example on a new experiment revision or
  newly assigned system tags. A tag edit that was prepared from older data then gets `412`.
  The client reloads and retries.
- **Idempotency.** Every POST requires `Idempotency-Key`. Keys follow the base contract:
  scoped to method and route, retained for 24 hours, replayed with
  `Idempotent-Replayed: true`, `409 IDEMPOTENCY_CONFLICT` for a different body, and
  `409 COMMAND_IN_PROGRESS` with `Retry-After` while the first request is still committing.
- **Atomicity.** Each catalog mutation commits atomically together with its idempotency
  record and its outgoing event outbox entry. The outbox is relayed to the legacy event
  stream after commit and on restart; a crash may duplicate delivery, never the mutation. Catalog writes do not share a transaction with legacy
  records. Legacy commands never wait on the catalog.
- **Recovery.** A corrupt catalog returns `503 SERVICE_UNAVAILABLE`; it is never automatically
  replaced or renamed. Restore its SQLite backup before resuming. If a catalog is absent,
  the projection can be rebuilt with stable IDs, but user-authored content and metadata
  require a backup. Back up the API data volume and project artifact volume together.

## 12. Events

One new project event type is delivered through the existing
`GET /projects/{project_id}/events` stream:

```ts
type CatalogChange = {
  entity: "file" | "tag" | "collection" | "relation",
  id: ID | null,              // tag slug for tags; null with bulk=true
  revision: number | null,    // null for relations and deletions
  deleted: boolean,
  bulk?: true                 // many changes (e.g. backfill); refetch the affected lists
}
// EventPayloads["catalog.changed"] = { changes: CatalogChange[] }   // 1..100 entries
```

Delivery rules:

- An event is emitted after each successful catalog mutation in this document, and after
  any projection pass that created or changed files or system relations.
- Delivery is at least once and may be duplicated. Catalog events may arrive after legacy
  events about the same underlying change. The event carries IDs, not full objects.
- On receiving the event, refetch affected resources and lists, including derived tag and
  collection counts. Equal-revision responses may refresh derived counts; only responses
  with an older revision must be discarded. Bulk events invalidate the whole named list.
- No-op PATCHes, already-present membership operations, and idempotent replays emit no new
  events. The original committed mutation may still be redelivered by the outbox.
- Clients that ignore this event type stay correct by refetching lists, as the base
  contract allows. Legacy event types and payloads are unchanged.

## 13. Errors added

| Status | Code | When |
|---|---|---|
| 409 | `FILE_READ_ONLY` | Changing name, content, or status of an artifact or record file. |
| 409 | `COLLECTION_READ_ONLY` / `COLLECTION_NOT_EMPTY` | Manual membership edit on a saved filter, or switching modes with explicit members. |
| 409 | `FILE_KIND_UNSUPPORTED` | Note-only route used on another file kind. |
| 409 | `TAG_EXISTS` | `POST /tags` with an existing slug. |
| 409 | `TAG_PROTECTED` | Deleting a system tag. |
| 409 | `RELATION_PROTECTED` | Deleting a system relation. |
| 413 | `PROJECT_QUOTA_EXCEEDED` | Note revision budget exceeded. |
| 422 | `VALIDATION_FAILED` / `INVALID_REFERENCE` | Section 9 limits, or IDs outside the project. |
| 503 | `SERVICE_UNAVAILABLE` | Catalog cannot be opened or locked (retryable). |

All other statuses and codes follow the base contract's section 9.

## 14. Compatibility

- This contract is additive under `/api/v1`. No legacy route, field, event, or status
  changes. `Workspace.counts` is unchanged and does not count notes.
- `contract_version` in `GET /session` stays `"1.0.0-draft"` until both contracts are
  consolidated. Detect support through `features.workspace_files`.
- A future agent tool that reads or writes notes or tags requires a contract amendment. It
  must keep the rule that notes are not evidence.
