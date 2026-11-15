# Stellaris frontend–backend contract

Contract version: **1.0.0-draft**  
Status: **Proposed implementation specification. No implementation is implied.**  
Prepared: **November 13, 2026**  
Source: the supplied “Stellaris — From question to discovery” product document for HackPrinceton 2026.

## 1. Purpose and scope

Additive backend extensions are specified in [research-contract.md](research-contract.md),
[hpc-contract.md](hpc-contract.md), [terminal-contract.md](terminal-contract.md),
and [agent-execution-contract.md](agent-execution-contract.md).
Their implementation/verification status is recorded in each document; legacy fields remain compatible.

This document defines the boundary between the Stellaris frontend and backend so they can be implemented independently. It specifies requests, responses, persistent resources, live events, errors, and scientific provenance for the first complete research workflow.

The MVP supports creating a project, asking a research question, collecting cited literature, designing an experiment, uploading or recording video, running isolated analysis, inspecting measurements and charts, and generating a Markdown report. Previously completed experiments remain accessible and carry their original execution dates.

The source document proposes React / Next.js, Python / Flask, an orchestrating agent, SQLite, project storage, and isolated workers. Those are implementation choices behind this boundary. The browser never calls an agent framework, literature provider, worker container, or project filesystem directly.

### Contract decisions introduced here

The product document does not define exact API shapes. This draft selects the following interoperable defaults:

- JSON REST API under `/api/v1` for reads and commands.
- One persistent chat history per project in the MVP.
- Server-sent events (SSE) for project progress, logs, and chat updates.
- Browser-managed camera preview and recording, followed by a completed-file upload. Live video streaming is outside the MVP.
- Server-side session authentication through a same-origin deployment.
- Immutable run inputs and output artifacts, with revisions for editable project and experiment records.
- Explicit resource links between sources, experiments, runs, measurements, and reports.

**Amendment (2026-11-14), implemented:** The [file workspace contract](file-workspace-contract.md) adds a free-form, tag-based file interface. It covers files, notes, tags, collections, and relations. For new workspace UI, it supersedes the rigid per-category navigation. Every backend route, resource, and event in this document stays in place and unchanged. These routes remain authoritative for scientific records and commands.

**Implementation update (2026-11-14):** The catalog backend foundation is implemented. Its frontend is named Materials and uses `/projects/:project_id/materials`. The removed `/projects/:project_id/workspace` was a frontend page, distinct from the unchanged backend workspace snapshot API. Knowledge graph draws explicit catalog relations in the browser using `/files` and `/relations`. Tracker uses existing runs and their persisted states. These views add no inferred scientific links, new graph endpoint, or independent task model.

**Proposed research desk extension (2026-11-14), not implemented:** The public [widget specification](research-workspace-spec.md), [Materials views specification](materials-views-spec.md), and [Reports specification](reports-spec.md) define the next UI. [File workspace section 16](file-workspace-contract.md#16-proposed-curated-views-extension) specifies optional `features.workspace_views`, collection presentation metadata, and artifact-kind selection. These are proposed additive catalog changes. Existing scientific commands, resource meaning, run snapshots, chart artifacts, and report generation remain authoritative here. Reports gain a proposed frontend index, not a new backend report resource.

“MUST” means an implementation requirement within this proposed contract. “SHOULD” allows an exception when its consequence is documented. All routes below belong to the MVP unless explicitly marked as future work.

## 2. Responsibilities at the boundary

### Frontend

- Own Research Chat, Research Canvas, Experiment Studio, Execution Panel, and Project Workspace rendering.
- Request camera or microphone permission through browser APIs only after a user action. Show recording controls and stop media tracks when capture ends or the user leaves capture mode.
- Keep preview and unsubmitted recordings local. Ask the user to upload the completed recording before sending its bytes.
- Submit commands, display server validation, and show queued, running, failed, cancelled, and completed states accurately.
- Render persisted evidence and results. Treat streamed text as a draft until its message is finalized.
- Preserve command identifiers during retries and reconnect event streams after interruption.

### Backend

- Own authentication, project access, validation, persistence, resource revisions, and authoritative run state.
- Route agent tools, retrieve literature, execute isolated work, and collect results.
- Store original inputs, code, environment information, logs, outputs, citations, and processing parameters.
- Enforce execution restrictions and required approvals independently of the UI.
- Publish committed resource changes through ordered events.
- Return safe project-scoped artifact URLs. Never expose local paths, container mounts, provider credentials, or internal agent state.

The frontend may show optimistic pending indicators. It MUST NOT manufacture successful runs, citations, scientific measurements, or completed reports.

## 3. Transport, authentication, and common rules

### HTTP and identity

- Production traffic uses HTTPS. The frontend and API share an origin, with a development proxy if needed.
- A successful login establishes an `HttpOnly`, `Secure`, `SameSite=Lax` session cookie. Local HTTP development may omit `Secure`.
- `GET /session` returns the current user and a CSRF token. The authentication provider and login screen are a separate integration dependency, not specified by the product document.
- Mutating requests require `X-CSRF-Token`. The backend also validates their `Origin`.
- Every resource lookup checks the authenticated user's project access, including event streams and binary downloads.
- Unauthenticated requests return `401`. A resource outside the user's access returns `404` to avoid exposing its existence. An authorized user lacking a permitted action receives `403`.

### Development mode without authentication (user-approved, current implementation)

The user explicitly approved omitting authentication for now. Until an authentication provider is selected, the backend runs in this mode and the session/CSRF rules above are not enforced:

- The API is published on loopback only (`127.0.0.1`). It MUST NOT be exposed beyond the local machine in this mode.
- `GET /session` is a development compatibility response: a fixed local user, `csrf_token: ""`, and an additional `auth_mode: "development_none"` field. `X-CSRF-Token` is ignored and `401` is never returned.
- Mitigations retained: requests with a `Host` outside the configured loopback names return `403 ACTION_FORBIDDEN`; mutating requests carrying an `Origin` outside the configured allow-list return `403 CSRF_FAILED`; JSON bodies require `Content-Type: application/json` (`415` otherwise).
- Project IDs are not an authorization boundary. Project-scoped references and execution isolation are still enforced.
- Idempotency keys are scoped to method and route (there is no user). A missing `Idempotency-Key` returns `428 PRECONDITION_REQUIRED`. Replayed responses carry `Idempotent-Replayed: true`.

### Backend topology (implementation detail, not a browser contract)

One Docker Compose configuration runs the primary backend. Creating a project creates a dedicated project container and a persistent named volume (project data plus the project agent's scratch space); the container stays running for the project's duration, including while archived. Scientific code runs in separate temporary isolated containers per run. Only the primary backend controls Docker; project and worker containers never receive the Docker socket or host filesystem access. None of these paths, names, or mounts appear in API responses.

### Serialization

- Request and response JSON uses `snake_case`. TypeScript below documents the wire shape and does not mandate a frontend implementation language.
- IDs are opaque strings. Clients MUST NOT derive meaning or paths from them.
- Timestamps use RFC 3339 UTC strings, such as `2026-11-14T00:00:00Z`.
- Durations and media offsets use explicitly named units such as `duration_ms` and `time_s`.
- JSON numbers must be finite. Unknown values use an explicitly nullable field, not `NaN`, `Infinity`, or a fabricated zero.
- Fields are required unless marked `?`. A nullable field is present with `null` when its value is unavailable. An omitted PATCH field is unchanged. A supplied `null` clears only a nullable field.
- Responses may gain optional fields. Clients ignore unknown response fields. Requests reject unknown fields with `422` so spelling errors do not silently change behavior.
- JSON responses carry `X-Request-ID`. The frontend may include that identifier in support messages.

### Pagination

All list routes return `Page<T>`. They accept `limit` from 1 to 100, default 50, and an optional opaque `cursor`. Default ordering is ascending `(created_at, id)` unless a route states otherwise. Cursors preserve the original filters. Project lists use descending `(updated_at, id)` and may move as projects change.

```ts
type ID = string
type Timestamp = string
type Json = null | boolean | number | string | Json[] | { [key: string]: Json }
type Page<T> = { items: T[], next_cursor: string | null }
type Session = {
  user: { id: ID, display_name: string },
  csrf_token: string,
  contract_version: "1.0.0-draft"
}
```

### Retries and concurrent edits

- Every JSON POST requires `Idempotency-Key`, an opaque value created for that user action.
- Keys are scoped to user, method, and route and retained for at least 24 hours. Repeating the same key and canonical JSON body returns the original status and response. A different body returns `409 IDEMPOTENCY_CONFLICT`.
- The same command submitted while its first request is still committing returns `409 COMMAND_IN_PROGRESS` with `Retry-After`. The client retries with the same key.
- Editable `Project` and `Experiment` resources have integer `revision` values. GET, POST, and PATCH responses for those resources include an ETag containing the revision, for example `ETag: "3"`.
- PATCH requires `If-Match` with that ETag. Missing it returns `428 PRECONDITION_REQUIRED`. A stale value returns `412 REVISION_CONFLICT`. The frontend reloads and lets the user reconcile edits.
- Commands that create a run or submit a chat message return `202` after committing the run, not after completing execution.

## 4. Capability discovery

`GET /capabilities` → `200 Capabilities`.

The frontend reads capabilities before showing upload or execution options. Limits are server-authored values returned at runtime. This draft does not claim that a particular upload size or compute budget has already been configured.

```ts
type Capabilities = {
  api_version: "v1",
  model_provider?: "bedrock" | "openai" | null,
  model_configured?: boolean,
  features: {
    research_chat?: boolean,
    literature_search: boolean,
    experiment_design: boolean,
    video_analysis: boolean,
    image_analysis: boolean,
    audio_analysis: boolean,
    markdown_reports: boolean,
    remote_compute: boolean,
    collaboration: boolean
  },
  uploads: {
    accepted_mime_types: string[],
    max_file_bytes: number,
    max_video_duration_ms: number,
    max_project_bytes: number
  },
  execution: {
    allowed_backends: ("isolated_python")[],
    // Optional, additive and informational; clients must tolerate its absence. Lists both
    // descriptors when workers are available and is [] otherwise. It does not change validation.
    analysis_pipelines?: {
      id: "bouncing_ball_v1" | "python_analysis_v1",
      description: string,
      requires_code_artifact: boolean
    }[],
    max_wall_time_s: number,
    max_memory_mb: number,
    max_cpu_cores: number,
    network_access: false
  },
  literature_providers: ("arxiv" | "openalex" | "semantic_scholar")[],
  event_retention_seconds: number,
  max_log_chunk_bytes: number
}
```

When uploads, execution, events, or logs are not yet available, their numeric limits are `0`, their lists are empty, and the related features are `false`. A disabled feature returns `409 FEATURE_UNAVAILABLE` if requested directly. Browser camera availability is detected by the frontend and is separate from backend video-analysis support. Browser-produced media MIME types must intersect `accepted_mime_types`. If they do not, the UI offers a supported file upload.

`model_configured` reports only whether the selected provider's required settings are present and locally valid. It does not certify credentials, IAM permissions, model access, or a successful live invocation. Provider selection and credential values stay on the backend. The current default is AWS Bedrock with Amazon Nova; OpenAI is an explicit optional alternative. No credential values appear in capabilities.

Project quotas include space reserved for each accepted run's bounded logs and provenance. A run may be rejected with `413 PROJECT_QUOTA_EXCEEDED` when its audit reservation cannot fit. Ordinary uploads and generated outputs cannot consume that reserved space. If the underlying storage itself becomes unavailable, the backend retains its accepted snapshot and persisted log entries and explicitly warns `PROVENANCE_UNAVAILABLE` when no manifest artifact could be committed.

## 5. Core resource schemas

### Projects and workspace navigation

```ts
type Project = {
  id: ID,
  name: string,
  description: string,
  research_question: string | null,
  status: "active" | "archived",
  revision: number,
  created_at: Timestamp,
  updated_at: Timestamp
}

type Workspace = {
  project: Project,
  counts: {
    sources: number, experiments: number, runs: number, artifacts: number
  },
  active_run_ids: ID[],
  latest_report_artifact_id: ID | null,
  event_cursor: string
}
```

An archived project remains readable. It rejects new uploads, chat submissions, experiment edits, and run creation with `409 PROJECT_ARCHIVED`. It can be restored through a project PATCH. Already accepted runs may finish or be cancelled.

### Chat

```ts
type Message = {
  id: ID,
  project_id: ID,
  role: "user" | "assistant",
  content_markdown: string,
  attachment_ids: ID[],
  claim_ids: ID[],
  run_id: ID | null,
  status: "streaming" | "complete" | "interrupted",
  last_chunk_index: number | null,
  created_at: Timestamp,
  updated_at: Timestamp
}
```

User messages are stored as `complete`. Assistant messages start as `streaming`. `last_chunk_index` is `null` until any streamed chunk is persisted. A successful agent run finalizes its assistant message as `complete`. Failure or cancellation finalizes it as `interrupted`, preserving partial text and any committed evidence. Internal tool messages and hidden reasoning are not public message roles.

### Literature and citations

```ts
type Source = {
  id: ID,
  project_id: ID,
  provider: "arxiv" | "openalex" | "semantic_scholar" | "web" | "manual",
  external_id: string | null,
  title: string,
  authors: string[],
  published_at: string | null,
  doi: string | null,
  url: string,
  abstract: string | null,
  retrieval_status: "metadata_only" | "abstract_retrieved" | "full_text_retrieved" | "failed",
  retrieved_at: Timestamp,
  document_artifact_id: ID | null,
  created_at: Timestamp
}

type Citation = {
  source_id: ID,
  locator: string | null,
  excerpt: string | null
}
```

`published_at` preserves the provider's available date precision, for example `2024` or `2024-06-01`. A source identifies retrieved material and does not by itself establish a claim. Citation excerpts MUST come from retrieved material. When only metadata or an abstract is available, the backend cannot claim to have inspected the full paper. Source records are immutable snapshots. Later retrieval creates a new snapshot and does not rewrite an earlier report's citations.

### Experiment plans and calibration

```ts
type Variable = {
  name: string,
  role: "independent" | "dependent" | "controlled",
  description: string,
  unit: string | null
}

type Calibration =
  | { mode: "none", assumptions: string[] }
  | {
      mode: "reference_length",
      artifact_id: ID,
      frame_index: number,
      point_a_px: [number, number],
      point_b_px: [number, number],
      reference_length_m: number,
      reference_uncertainty_m: number | null,
      assumptions: string[]
    }

type Experiment = {
  id: ID,
  project_id: ID,
  title: string,
  hypothesis: string,
  method: "physical" | "computational" | "hybrid",
  protocol_markdown: string,
  variables: Variable[],
  success_criteria: string[],
  input_artifact_ids: ID[],
  calibration: Calibration,
  limitations: string[],
  revision: number,
  created_at: Timestamp,
  updated_at: Timestamp
}
```

An experiment is a plan, not an execution status. Execution history comes from its linked runs. A newly generated protocol cannot appear as a completed experiment.

For reference calibration, points refer to the decoded frame after orientation metadata is applied, with origin at its top-left and axes right/down. Points must be distinct, inside that frame, and refer to an attached video or image. `frame_index` is zero-based and is `0` for an image. Length is positive and uncertainty, when supplied, is nonnegative. A run records the resulting meters-per-pixel conversion and assumptions in its provenance.

No calibration means measurements remain in pixels or another supported native unit. Physical scale MUST NOT be invented. Dimensionless bounce-height ratios may be reported under explicit perspective, baseline, and physical-model assumptions.

### Files and generated artifacts

```ts
type Artifact = {
  id: ID,
  project_id: ID,
  experiment_id: ID | null,
  run_id: ID | null,
  kind: "document" | "dataset" | "image" | "video" | "audio" |
        "code" | "chart" | "report" | "log" | "environment",
  origin: "observed" | "derived" | "simulated" | "generated" | "reference",
  filename: string,
  mime_type: string,
  size_bytes: number,
  sha256: string,
  parent_artifact_ids: ID[],
  metadata: {
    width_px?: number,
    height_px?: number,
    duration_ms?: number,
    frame_count?: number,
    nominal_frame_rate_fps?: number,
    recorded_at?: Timestamp,
    uploaded_at?: Timestamp
  },
  created_at: Timestamp
}
```

Artifacts become immutable once ready. Filenames are labels, never filesystem paths. The backend computes hashes and inspects media metadata. It does not trust client-supplied MIME types or timing claims. `nominal_frame_rate_fps` is informational. Analysis uses actual decoded timestamps for variable-frame-rate video.

`observed` denotes raw experimental data, including a user declaration for uploaded recordings. It does not certify authenticity. `derived` denotes processing of existing inputs. `simulated` identifies synthetic experimental data. `generated` identifies authored code, reports, or other generated documents. `reference` denotes retrieved reference material. An uploaded simulation must retain `simulated` origin through its derived results.

### Runs and reproducibility

```ts
type RunInput =
  | {
      kind: "agent",
      user_message_id: ID,
      assistant_message_id: ID,
      attachment_ids: ID[],
      context_artifact_ids: ID[]
    }
  | {
      kind: "analysis",
      experiment_id: ID,
      experiment_revision: number,
      input_artifact_ids: ID[],
      pipeline: "bouncing_ball_v1" | "python_analysis_v1",
      code_artifact_id: ID | null,
      parameters: { [key: string]: Json }
    }
  | {
      kind: "report",
      experiment_id: ID,
      evidence_run_ids: ID[],
      source_ids: ID[],
      title: string,
      format: "markdown"
    }

type RunStatus = "queued" | "running" | "awaiting_approval" |
                 "cancelling" | "succeeded" | "failed" | "cancelled"

type Run = {
  id: ID,
  project_id: ID,
  input: RunInput,
  status: RunStatus,
  phase: string | null,
  progress: { fraction: number | null, message: string | null },
  execution_backend: "isolated_python",
  output_artifact_ids: ID[],
  result_summary: string | null,
  error: { code: string, message: string, retryable: boolean } | null,
  provenance_artifact_id: ID | null,
  created_at: Timestamp,
  started_at: Timestamp | null,
  finished_at: Timestamp | null,
  revision: number
}
```

Progress fraction is between 0 and 1, or `null` when indeterminate. Phase is display text, not a client state machine. Run revision increases for every persisted run change and prevents an older event from overwriting newer data.

The backend snapshots the complete experiment definition, referenced artifact hashes, parameters, code, selected sources, and execution limits when it accepts a run. It persists the snapshot before enqueueing work. Later plan edits do not alter that run. Agent runs also snapshot the preceding chat and relevant project context. Tools may create new artifacts and experiment revisions, which are recorded as outputs.

`provenance_artifact_id` points to a JSON manifest containing the accepted input snapshot, code hashes, container image digest, Python version, package versions, tool/pipeline versions, seeds when applicable, calibration conversion, observed timestamps, and model/provider identifiers used. It also records partial outputs and known reproducibility limits after failure. Secrets and hidden reasoning are excluded.

The execution backend refers to scientific-code execution. Agent coordination and remote literature retrieval happen through backend-controlled tools outside the worker's network restriction.

### Measurements, evidence, and conclusions

```ts
type EvidenceRef = {
  artifact_id: ID,
  frame_index: number | null,
  time_s: number | null,
  row_index: number | null
}

type Measurement = {
  id: ID,
  project_id: ID,
  experiment_id: ID,
  run_id: ID,
  series: string,
  quantity: string,
  value: number | null,
  unit: string,
  time_s: number | null,
  uncertainty: {
    absolute: number | null,
    method: string | null
  },
  status: "valid" | "missing" | "rejected",
  evidence: EvidenceRef[],
  calibration_mode: "none" | "reference_length",
  data_origin: "observed" | "derived" | "simulated",
  assumptions: string[],
  created_at: Timestamp
}

type Claim = {
  id: ID,
  project_id: ID,
  run_id: ID,
  kind: "observation" | "inference" | "hypothesis",
  text: string,
  measurement_ids: ID[],
  citations: Citation[],
  evidence: EvidenceRef[],
  assumptions: string[],
  limitations: string[],
  created_at: Timestamp
}

type RunResults = {
  run_id: ID,
  measurement_count: number,
  claim_ids: ID[],
  chart_artifact_ids: ID[],
  annotated_media_artifact_ids: ID[],
  report_artifact_id: ID | null,
  warnings: { code: string, message: string }[]
}
```

Every measurement links to evidence, including the code or dataset behind a simulated measurement. `valid` requires a finite value. `missing` and `rejected` require `value: null` and an explanation in assumptions. Uncertainty uses the same unit as the value. Unknown uncertainty stays `null` and does not mean zero error. Units include `px`, `s`, `m`, `m/s`, `m/s^2`, and `1` for dimensionless quantities.

An observation requires evidence or measurement links. An inference requires evidence, measurements, or citations and states its assumptions. A hypothesis is visibly labeled as proposed. AI text alone is not experimental evidence. A report built from simulated inputs labels the affected results as simulated even when its own artifact origin is `generated`.

## 6. REST endpoints

All routes in this section are relative to `/api/v1`. Routes nested under a project enforce that every referenced resource belongs to that project. Cross-project references return `422 INVALID_REFERENCE` without disclosing the other project.

### Session and projects

- `GET /session` → `200 Session`. An expired session returns `401`. In development mode (section 3) this returns the fixed compatibility session and never `401`.
- `GET /health` → `200 { status: "ok", database: "ok", docker: "ok" }`, or `503` with the same shape and `status: "degraded"` when a dependency is unavailable. Operational endpoint, not a product resource.
- `GET /projects` → `200 Page<Project>`. Optional query: `status=active|archived`.
- `POST /projects` with `{ name, description?, research_question? }` → `201 Project` and `Location`. Name must contain 1–120 non-whitespace characters. Description defaults to `""`, research question to `null`, and status to `active`. The `201` is returned only after the project's dedicated workspace is running. If it cannot be provisioned, the response is `503 SERVICE_UNAVAILABLE` (retryable, `Retry-After`), the project is not listed or retrievable, and retrying with the same `Idempotency-Key` resumes provisioning of the same project.
- `GET /projects/{project_id}` → `200 Project` and ETag.
- `PATCH /projects/{project_id}` with any of `{ name, description, research_question, status }` → `200 Project` and a new ETag. At least one field is required. While archived, only a PATCH that sets `status: "active"` (optionally with other fields) is accepted; others return `409 PROJECT_ARCHIVED`. A PATCH that changes nothing returns the unchanged revision.
- `GET /projects/{project_id}/workspace` → `200 Workspace`. Its cursor and summary reflect one consistent project snapshot.

Project hard deletion is not an MVP operation. Archiving avoids removing evidence or breaking existing reports.

### Research Chat and Canvas

- `GET /projects/{project_id}/messages` → `200 Page<Message>`.
- `GET /projects/{project_id}/messages/{message_id}` → `200 Message`.
- `POST /projects/{project_id}/messages` with `{ content_markdown, attachment_ids?, context_artifact_ids? }` → `202 { user_message: Message, assistant_message: Message, run: Run }`. Text must be nonempty. Both arrays default to empty. The backend atomically creates the user message, assistant placeholder, and queued agent run.
- `GET /projects/{project_id}/sources` → `200 Page<Source>`. Optional filter: `provider`.
- `GET /projects/{project_id}/sources/{source_id}` → `200 Source`.
- `POST /projects/{project_id}/sources` with `{ title, authors?, url, doi?, published_at?, abstract? }` → `201 Source` with `provider: "manual"`, `retrieval_status: "metadata_only"`, and no document artifact. Author names default to an empty array. Other optional metadata defaults to `null`.
- `GET /projects/{project_id}/claims` → `200 Page<Claim>`. Optional filter: `run_id`.
- `GET /projects/{project_id}/claims/{claim_id}` → `200 Claim`.

Literature discovery and experiment-design requests travel through chat in the MVP. The agent saves sources, claims, and experiments through backend tools using these same public resource rules. This contract does not expose vendor search payloads or agent framework data structures.

### Experiment Studio

- `GET /projects/{project_id}/experiments` → `200 Page<Experiment>`.
- `POST /projects/{project_id}/experiments` → `201 Experiment` and ETag. Body is `Experiment` without server-managed `id`, `project_id`, `revision`, `created_at`, and `updated_at`. All remaining fields are required. Initial revision is `1`.
- `GET /projects/{project_id}/experiments/{experiment_id}` → `200 Experiment` and ETag.
- `PATCH /projects/{project_id}/experiments/{experiment_id}` → `200 Experiment` and new ETag. Accepts any nonempty subset of the creation fields. Arrays replace the full existing array.

Artifact IDs in an experiment must already be ready. The backend rejects uncommitted uploads. Plan validation does not imply an experiment has been performed.

### File upload and workspace artifacts

- `POST /projects/{project_id}/uploads` with `UploadRequest` → `201 Upload`.
- `GET /projects/{project_id}/uploads/{upload_id}` → `200 Upload`.
- `PUT /projects/{project_id}/uploads/{upload_id}/content` sends raw bytes → `204`. `Content-Type` matches the declared MIME type. Browser-managed transfer encoding is accepted. The backend counts actual bytes rather than relying on `Content-Length`.
- `POST /projects/{project_id}/uploads/{upload_id}/complete` with `{}` → `200 Artifact` after validation and artifact persistence.
- `GET /projects/{project_id}/artifacts` → `200 Page<Artifact>`. Optional filters: `kind`, `experiment_id`, `run_id`.
- `GET /projects/{project_id}/artifacts/{artifact_id}` → `200 Artifact`.
- `GET /projects/{project_id}/artifacts/{artifact_id}/content` → binary content with the stored `Content-Type`, ETag equal to the SHA-256 hash, and `Content-Disposition: attachment` by default. `?disposition=inline` is allowed only for approved image, audio, video, and plain-text types. HTML and SVG never execute in the app origin.

```ts
type UploadRequest = {
  filename: string,
  mime_type: string,
  size_bytes: number,
  sha256?: string,
  kind: "document" | "dataset" | "image" | "video" | "audio" | "code",
  origin: "observed" | "simulated" | "reference" | "generated",
  experiment_id?: ID,
  capture?: {
    method: "browser_camera" | "browser_microphone" | "file_upload",
    recorded_at: Timestamp | null,
    recording_permission_confirmed: boolean
  }
}

type Upload = {
  id: ID,
  project_id: ID,
  request: UploadRequest,
  status: "pending" | "uploaded" | "completed" | "failed" | "expired",
  artifact_id: ID | null,
  expires_at: Timestamp,
  error: { code: string, message: string } | null
}
```

Upload sequence is create → transfer → complete. Uploads are invisible to scientific workflows until completion. Capture metadata is required for browser camera/microphone recordings, with `recording_permission_confirmed: true`. It records the client's assertion of consent and is not a substitute for browser permission. File imports do not require camera permission.

The backend verifies size, optional hash, media type, decodability, and duration before publishing an artifact. A validation failure marks the upload failed and returns the relevant error. Expired uploads return `410 UPLOAD_EXPIRED`. Incomplete temporary bytes are eligible for cleanup after expiry. A completed artifact is independent of its upload's expiry.

The content PUT is restartable, not chunk-resumable. An interrupted transfer never marks the upload as `uploaded`. A retry replaces incomplete temporary bytes. After a successful transfer, another PUT with the same actual hash and byte count returns `204`. Different bytes return `409 UPLOAD_CONTENT_CONFLICT`. Concurrent transfers for one upload return `409 UPLOAD_IN_PROGRESS`. Completion is atomic and always returns the same artifact for a completed upload, including after an idempotency-key retention window expires.

Binary responses support single HTTP byte ranges and return `206` or `416` as appropriate, so videos can seek. The frontend retrieves a report's `.md` artifact through the same content route. It renders Markdown with HTML disabled and sanitized links.

### Execution Panel and reports

- `GET /projects/{project_id}/runs` → `200 Page<Run>`. Optional filters: `experiment_id`, `status`, `kind`.
- `POST /projects/{project_id}/runs` with an `analysis` or `report` member of `RunInput` → `202 Run`. Agent runs are created through chat only.
- `GET /projects/{project_id}/runs/{run_id}` → `200 Run`.
- `POST /projects/{project_id}/runs/{run_id}/cancel` with `{}` → `202 Run` while cancellation is pending, or `200 Run` if already terminal.
- `GET /projects/{project_id}/runs/{run_id}/results` → `200 RunResults`, including partial results while execution continues.
- `GET /projects/{project_id}/runs/{run_id}/measurements` → `200 Page<Measurement>`. Optional filter: `series`.
- `GET /projects/{project_id}/runs/{run_id}/logs` → `200 Page<LogEntry>`. Optional `after_sequence` selects entries strictly after that sequence. A supplied cursor retains that filter.

```ts
type LogEntry = {
  id: ID,
  run_id: ID,
  sequence: number,
  stream: "stdout" | "stderr" | "system",
  text: string,
  created_at: Timestamp
}
```

Logs have strictly increasing per-run sequence numbers. Text is escaped when displayed and credentials are redacted before persistence. Chunks respect `max_log_chunk_bytes`. Complete retained logs also become a log artifact. If output is truncated by a server limit, a system entry and result warning explicitly record that fact.

Analysis run validation requires the submitted experiment revision to match the current one. A stale revision returns `409 EXPERIMENT_REVISION_CONFLICT`. Input artifacts must be a nonempty subset of that plan's inputs. `python_analysis_v1` requires a ready Python code artifact. `bouncing_ball_v1` requires exactly one supported video and `code_artifact_id: null`. It persists the exact executed pipeline code as an output artifact.

For `bouncing_ball_v1`, the allowed parameters are `start_time_s` (default `0`), `end_time_s` (default `null`, meaning media end), and `object_hint` (default `"ball"`). The interval must be within the video and have positive duration. Unknown parameters are rejected. `object_hint` is provenance metadata only: it is recorded in output metadata and does not select a detector or change the algorithm, which always tracks one bouncing ball. It cannot make the pipeline count fingers or recognize gestures. Calibration comes from the plan snapshot. The pipeline records its selected baseline, detection method, and any failed detections in provenance. For `python_analysis_v1`, parameters are a JSON object passed to the isolated script, whose exact input/output interface is documented in section 10.

A report request accepts committed evidence from terminal analysis runs, including clearly labeled partial evidence from failed or cancelled runs. At least one evidence run is required and all evidence runs must reference the requested experiment. Methods and calibration descriptions come from each evidence run's accepted snapshot, including when the current experiment has since changed. The report must describe failures and missing measurements. It cannot claim success just because report generation succeeded. Draft research summaries without executed evidence remain chat output in the MVP.

Markdown reports contain the research question, hypothesis, citations, input IDs, method, code/run links, calibration assumptions, measurements, plots, uncertainty, limitations, and a provenance link. In-project links use authenticated API content routes or public source URLs. The generated report is an immutable UTF-8 `.md` artifact. `report_artifact_id` remains `null` until that artifact is committed.

**Agent-led report extension, implemented with provider-free local checks (November 14, 2026):** Report generation invokes the configured LangChain Deep Agent in the owning project container to analyze saved evidence and assess the hypothesis. The canonical requirements and acceptance scenarios are in [Reports: required agent-led analysis](reports-spec.md#required-agent-led-analysis). Interpretation must address contradictions, alternative explanations, uncertainty, failures, and inconclusive evidence with supporting references. Rephrasing summaries and assembling tables alone are insufficient. Observations, computed results, and AI interpretations remain distinct. New calculations use existing isolated execution tools with retained code, inputs, outputs, and provenance. Report provenance records model identity, evidence supplied or read, truncation, limitations, and calculation runs. Provider failure fails the run rather than silently publishing a deterministic substitute. Existing report request fields, lifecycle, immutable evidence, and saved deterministic report reading remain compatible. `features.markdown_reports` requires locally valid model configuration. The report agent uses paged evidence tools and returns an internally validated assessment, interpretation, limitations, and record references. Calculation child runs publish computed datasets/charts without creating new scientific measurements or claims or inheriting a camera conversion from another run. Existing public request fields are unchanged. See [verification and live-provider limits](verification/report-analysis.md).

## 7. Run states and approval contract

Allowed transitions:

```text
queued            -> running | cancelled | failed
running           -> awaiting_approval | cancelling | succeeded | failed
awaiting_approval -> running | cancelling | cancelled | failed
cancelling        -> cancelled | failed
succeeded         -> terminal
failed            -> terminal
cancelled         -> terminal
```

Run acceptance and cancellation serialize against completion. If completion commits before cancellation, cancel returns the completed run. Once `cancelling` commits, the run cannot become `succeeded`. The backend stops worker execution, records partial artifacts, and sets the final state. Cancellation does not remove prior evidence.

Retrying a failed scientific operation creates a new run with a new idempotency key. Reusing the original run-creation key returns the original run, even if it failed. Restarts preserve run records. An execution lost during recovery becomes `failed` with `WORKER_LOST` rather than being silently rerun with possible duplicate effects.

### Approval boundary

MVP Python execution uses the published isolation limits and no network access. It cannot access a host filesystem, launch unrestricted processes, or submit HPC jobs. The backend rejects unsupported execution rather than treating approval as a way around those limits.

If an agent proposes an operation that is supported but requires explicit authorization, it persists an approval before proceeding:

```ts
type Approval = {
  id: ID,
  project_id: ID,
  run_id: ID,
  action_type: "paid_tool_call",
  summary: string,
  action_snapshot: { [key: string]: Json },
  action_sha256: string,
  estimated_cost: { amount: number, currency: string } | null,
  status: "pending" | "approved" | "rejected" | "expired",
  created_at: Timestamp,
  expires_at: Timestamp,
  decided_at: Timestamp | null
}
```

- `GET /projects/{project_id}/runs/{run_id}/approvals` → `200 Page<Approval>`.
- `POST /projects/{project_id}/approvals/{approval_id}/decision` with `{ decision: "approve" | "reject", action_sha256 }` → `200 Approval`.

The approval UI displays the exact action snapshot and any cost uncertainty. Approval binds to that snapshot, submitting user, and single execution. Modified actions require a new approval. A repeated identical decision returns the stored result. A contradictory decision returns `409 APPROVAL_ALREADY_DECIDED`. A stale action hash returns `409 APPROVAL_CHANGED`.

Rejection or expiry cancels the run with an explanatory result warning. Cancellation or terminal failure expires its outstanding approval. A decision cannot resume a terminal run. Remote or privileged action types require a future contract extension and remain unavailable in this draft. Implementations with no paid tool integration never create approvals, but retain these resource and state shapes.

## 8. Live event contract

`GET /projects/{project_id}/events?after={event_cursor}` opens an authenticated `text/event-stream` response. Native `EventSource` uses the session cookie. Cross-origin event access is not enabled in the MVP.

Each event uses its cursor as the SSE `id`, its type as the SSE `event`, and a JSON `ProjectEvent` as its SSE `data`:

```text
id: evt_000042
event: run.updated
data: {"cursor":"evt_000042","project_id":"prj_demo","type":"run.updated","occurred_at":"2026-11-14T00:00:00Z","run_id":"run_demo","payload":{"run":{"id":"run_demo"}}}

```

The SSE block above abbreviates the Run object to demonstrate framing only. Actual `run.updated` events contain a complete `Run`.

```ts
type EventPayloads = {
  "project.updated": { project: Project },
  "message.created": { message: Message },
  "message.delta": {
    message_id: ID, chunk_index: number, text: string
  },
  "message.updated": { message: Message },
  "source.created": { source: Source },
  "experiment.updated": { experiment: Experiment },
  "upload.updated": { upload: Upload },
  "run.created": { run: Run },
  "run.updated": { run: Run },
  "run.log": { entry: LogEntry },
  "artifact.created": { artifact: Artifact },
  "measurements.available": { run_id: ID, total_count: number },
  "claim.created": { claim: Claim },
  "results.updated": { results: RunResults },
  "approval.required": { approval: Approval },
  "approval.updated": { approval: Approval }
}

type ProjectEvent = {
  [K in keyof EventPayloads]: {
    cursor: string,
    project_id: ID,
    type: K,
    occurred_at: Timestamp,
    run_id: ID | null,
    payload: EventPayloads[K]
  }
}[keyof EventPayloads]
```

Event rules:

1. Persist resources and their event records atomically before delivery. Events never point at an uncommitted artifact.
2. Order cursors per project. Delivery is at least once. Clients discard already-applied cursors and ignore unknown event types.
3. On an initial load, fetch Workspace and the required resource lists, then subscribe after its `event_cursor`. Events newer than list responses may repeat resources, so upsert by ID and revision rather than append blindly.
4. On reconnect, `Last-Event-ID` takes precedence over the original `after` query. Resume strictly after that cursor. Cursors are opaque and project-specific.
5. Expired cursors return `410 EVENT_CURSOR_EXPIRED` before opening the stream. An invalid cursor returns `400 INVALID_EVENT_CURSOR`. A fetch-based SSE client can inspect these statuses. With native EventSource, on a connection error the frontend closes the stream, refreshes Workspace and visible resource lists, then opens a new stream from the refreshed cursor. It must not retry a permanently failing connection indefinitely.
6. Send a comment heartbeat at least every 15 seconds while idle. Disable response buffering in the deployment proxy. Revalidate session access periodically and close the stream when access expires.
7. Message chunks use zero-based, increasing `chunk_index` per message. On a gap, fetch that Message and replace local text and `last_chunk_index`. Discard chunks at or below that index. Delta text is already persisted before publication. Ignore a delayed delta after the message has been finalized. `message.updated` supplies the complete authoritative body and status.
8. A terminal `run.updated` is emitted after committing final messages, output links, results, logs, and the provenance manifest. Individual artifact/result events may arrive earlier. A successful run cannot precede its own required outputs.

No WebSocket connection is required for the MVP. Camera previews stay in the browser. A future live-media protocol must define its own timestamps, buffering, consent, and transport rules.

## 9. Error contract

All JSON API failures use the following envelope, including validation, access, and server errors. Binary upload and download failures also use this JSON envelope when no successful body has started. A broken response after streaming begins is recovered by reconnection or an explicit resource GET.

```json
{
  "error": {
    "code": "CALIBRATION_REQUIRED",
    "message": "Physical distance requires a reference length. Use pixel units or add calibration.",
    "request_id": "req_demo",
    "retryable": false,
    "details": {
      "field_errors": [
        { "path": "/calibration", "message": "No physical scale is available." }
      ]
    }
  }
}
```

`details` is a JSON object and defaults to `{}`. Field paths use JSON Pointer notation. Error codes, rather than message text, drive UI behavior.

- `400`: malformed JSON (`MALFORMED_JSON`), invalid query (`INVALID_QUERY`, `INVALID_CURSOR`), invalid header (`INVALID_HEADER`), or invalid event cursor.
- `401`: `AUTH_REQUIRED` or `SESSION_EXPIRED`.
- `403`: `ACTION_FORBIDDEN` or `CSRF_FAILED`.
- `404`: `RESOURCE_NOT_FOUND`.
- `409`: state or command conflicts, including `PROJECT_ARCHIVED`, `FEATURE_UNAVAILABLE`, `ARTIFACT_NOT_READY`, `COMMAND_IN_PROGRESS`, approval conflicts, and revision conflicts in submitted run inputs.
- `410`: expired upload or event cursor.
- `412`: `REVISION_CONFLICT` for an editable-resource ETag mismatch.
- `413`: `UPLOAD_TOO_LARGE` or `PROJECT_QUOTA_EXCEEDED`.
- `415`: `UNSUPPORTED_MEDIA_TYPE`.
- `422`: `VALIDATION_FAILED`, `INVALID_REFERENCE`, `MEDIA_DECODE_FAILED`, `HASH_MISMATCH`, `CALIBRATION_REQUIRED`, or `INSUFFICIENT_EVIDENCE`.
- `428`: `PRECONDITION_REQUIRED`.
- `429`: `RATE_LIMITED`, with `Retry-After`.
- `500`: `INTERNAL_ERROR`, without stack traces or private paths.
- `503`: `SERVICE_UNAVAILABLE`, with `Retry-After` when known.

Run error codes (`Run.error.code`, not HTTP statuses) used by the current backend: `EXECUTION_TIMEOUT`, `RESOURCE_LIMIT_EXCEEDED`, `WORKER_LOST`, `INVALID_OUTPUT` (section 10), `WORKER_FAILED` (analysis code exited non-zero), `WORKER_UNAVAILABLE` (the isolated worker could not be started), `INPUT_UNAVAILABLE` / `INPUT_INTEGRITY_FAILED` (stored input bytes unreadable or not matching the accepted snapshot's hash), `INSUFFICIENT_EVIDENCE` (the pipeline could not support its measurements; committed partial evidence remains), `PROJECT_QUOTA_EXCEEDED`, `FEATURE_UNAVAILABLE`, and `INTERNAL_ERROR`. `POST /runs` returns `409 EXPERIMENT_REVISION_CONFLICT` for a stale `experiment_revision` (section 6).

An external search provider or worker failing after run acceptance changes the persisted Run to `failed` when no useful continuation is possible. It does not retroactively change the accepted HTTP response. Partial source retrieval may instead yield a successful research run with explicit warnings and the available citations.

Clients retry only transient failures using bounded exponential backoff and the original idempotency key. They do not automatically rerun failed scientific work, grant permission, approve an action, or resubmit changed inputs.

## 10. Scientific worker boundary visible through the API

Worker implementation is internal, but the API guarantees the following behavior:

- Code runs in an isolated environment with only declared input files, a writable output directory, and published CPU, memory, and wall-time limits.
- Workers have no host filesystem access or outbound network. Backend literature tools retrieve references separately.
- `python_analysis_v1` receives an immutable `/input/manifest.json` containing artifact IDs, hashes, read-only worker-local paths, experiment/calibration snapshot, and `parameters`. Worker-local paths never appear in public Artifact responses.
- The script writes `/output/result.json` with `measurements`, `claims`, `artifacts`, and `warnings` arrays using the worker output schema below. Worker-local keys connect newly produced records before the backend assigns public IDs.
- Each declared output artifact supplies a unique `local_key`, relative `path`, `kind`, `origin`, `mime_type`, and parent references. The backend rejects absolute/traversing paths, symlinks, missing files, unknown evidence references, cyclic parent links, non-finite values, and files outside the output directory. It assigns IDs, computes hashes, and resolves local references before publication.
- A valid exit code alone does not imply a valid result. A missing or invalid manifest fails the run with `INVALID_OUTPUT`. Schema-valid measurements unsupported by any evidence are also rejected.
- Code may report limitations or no valid detections. Those outcomes are shown accurately. The backend does not replace missing physical observations with invented or simulated data.
- Timeouts and resource exhaustion fail with `EXECUTION_TIMEOUT` and `RESOURCE_LIMIT_EXCEEDED`. Worker interruption uses `WORKER_LOST`. Retained partial logs and artifacts remain inspectable.

Reports do not execute embedded code in the browser. Charts are initially immutable image artifacts linked to measurements or data artifacts, avoiding a requirement for a specific interactive charting library.

```ts
type WorkerArtifactRef =
  | { input_artifact_id: ID }
  | { output_artifact_key: string }
type WorkerEvidence = Omit<EvidenceRef, "artifact_id"> & {
  artifact: WorkerArtifactRef
}
type WorkerMeasurement = Omit<Measurement,
  "id" | "project_id" | "experiment_id" | "run_id" | "created_at" | "evidence"
> & { local_key: string, evidence: WorkerEvidence[] }
type WorkerClaim = Omit<Claim,
  "id" | "project_id" | "run_id" | "created_at" | "measurement_ids" | "evidence"
> & {
  local_key: string,
  measurement_keys: string[],
  evidence: WorkerEvidence[]
}
type WorkerResult = {
  measurements: WorkerMeasurement[],
  claims: WorkerClaim[],
  artifacts: {
    local_key: string,
    path: string,
    kind: Artifact["kind"],
    origin: Artifact["origin"],
    mime_type: string,
    parents: WorkerArtifactRef[]
  }[],
  warnings: { code: string, message: string }[]
}
```

Current backend rules for worker output (implementation additions within this section's intent): worker artifacts may only have origin `derived`, `simulated`, or `generated` and may not be `report` artifacts; when any analysed input is `simulated`, derived outputs, measurements, and claims are relabelled as simulated and a `ORIGIN_RELABELLED` result warning records it. Measurement units are limited to `px`, `px/s`, `px/s^2`, `s`, `m`, `m/s`, `m/s^2`, and `1`, except that script analyses of uploaded tabular inputs may also report a short source-column unit label (for example `in`, `lb`, `kg/m^2`, `%`; letters, digits and `%/^*().-`, at most 32 characters) when the measurement's assumptions state the source column and unit; metre-based units require a `reference_length` calibration snapshot, and `calibration_mode` must equal the snapshot's mode. A worker warning with code `INSUFFICIENT_EVIDENCE` fails the run with that error code while its validated results are still committed as partial evidence.

Measurement and claim keys must be unique within their respective arrays. `measurement_keys` references measurements in that result. `input_artifact_id` references only declared run inputs, including the selected code artifact. Worker claims may cite only sources in the accepted context snapshot. The backend populates all public ownership fields and timestamps, uses the final path segment as the artifact filename, and derives media metadata itself. Worker output never assigns a public project, run, or artifact ID.

## 11. End-to-end bouncing-ball integration sequence

1. The frontend calls `/session` and `/capabilities`, then creates a project with its research question.
2. It reads Workspace, subscribes to events from the returned cursor, and submits the user's research request through `/messages`.
3. The accepted agent run retrieves literature, saves sources and claims, and creates an Experiment containing its hypothesis, protocol, variables, calibration requirements, and limitations. The frontend renders those persisted records in Research Canvas and Experiment Studio.
4. The user records a video through visible browser controls or selects an existing video. The frontend creates an Upload, transfers bytes, and completes it. No camera permission or recording starts because of an agent event alone.
5. The frontend PATCHes the Experiment with the returned artifact ID and any user-provided calibration, using its latest ETag.
6. It submits an analysis run with `pipeline: "bouncing_ball_v1"`, the current experiment revision, that video ID, `code_artifact_id: null`, and the selected parameters.
7. Events update progress and logs. The backend saves code, annotated frames/video, measurement data, charts, and provenance. The frontend fetches measurement pages and displays units, missing detections, assumptions, and uncertainty.
8. The user inspects bounce-height and energy-retention estimates. Under an appropriate fixed-mass, common-baseline model, height ratios can support dimensionless energy-retention estimates. The report states those assumptions and any perspective limitations.
9. The frontend submits a report run referencing the completed analysis and selected sources. The backend persists a Markdown report and emits final results.
10. Refreshing the project restores chat, experiment revisions, run histories, original media, measurements, sources, charts, and report links through REST. Event history is not the only way to recover project state.

A fallback demo opens an existing project/run with its original timestamp and visibly identifies it as a previously completed recording. It does not replay stored events as if a new physical experiment were running.

## 12. Compatibility and implementation handoff

Frontend and backend implementations use the resource shapes, status transitions, and event payloads in this document as their shared boundary. A framework-specific agent object is never a substitute for these resources.

Before integration, the teams need to supply the selected authentication provider and login entry point, deployed API origin/proxy, enabled literature-provider credentials, actual capability limits, and pinned versions of the first video pipeline and worker image. These are deployment inputs, not reasons to leave request or response shapes undefined.

Additive optional response fields and new events remain within `/api/v1`. Removing fields, changing units, changing field meaning, adding a new required request field, or introducing incompatible state behavior requires a new API version. The capability response must reflect actual configured availability.

This deliverable defines contracts only. It does not create backend routes, frontend components, worker infrastructure, automated tests, or a claim that the proposed system is already operational.

## 13. Future extensions, outside the MVP contract

- Microphone/audio analysis and synchronized multimodal inputs, enabled through capabilities only after their pipelines and timing contracts exist.
- Live camera/media streaming with a separate media transport contract.
- SSH, cloud, and Slurm/HPC execution with backend-specific job IDs, credentials handling, cost limits, explicit approval, and cancellation semantics.
- Multi-user collaboration with membership, roles, edit conflicts, and audit attribution.
- Multiple conversations and specialized agents without exposing internal orchestration messages.
- Run comparison, interactive scientific visualizations, notebooks, and citation graphs.
- Resumable multipart uploads and multi-device capture.
- PDF and DOCX exports as new report formats with their own capability flags.
- Destructive project/file deletion with an explicit authorization and evidence-retention policy.

These ideas come from the product vision or address later scaling needs. They are not promises of implemented behavior and do not block the initial research → experiment → measurement → Markdown-report workflow.


