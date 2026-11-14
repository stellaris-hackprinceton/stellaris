// Wire schemas from docs/frontend-backend-contract.md at the repository root.
export type ID = string
export type Timestamp = string
export type Json = null | boolean | number | string | Json[] | { [key: string]: Json }
export type Page<T> = { items: T[], next_cursor: string | null }
export type Session = {
  user: { id: ID, display_name: string },
  csrf_token: string,
  auth_mode?: 'development_none',
  contract_version: "1.0.0-draft"
}

export type Capabilities = {
  api_version: "v1",
  features: {
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
    max_wall_time_s: number,
    max_memory_mb: number,
    max_cpu_cores: number,
    network_access: false
  },
  literature_providers: ("arxiv" | "openalex" | "semantic_scholar")[],
  event_retention_seconds: number,
  max_log_chunk_bytes: number
}

export type Project = {
  id: ID,
  name: string,
  description: string,
  research_question: string | null,
  status: "active" | "archived",
  revision: number,
  created_at: Timestamp,
  updated_at: Timestamp
}

export type Workspace = {
  project: Project,
  counts: {
    sources: number, experiments: number, runs: number, artifacts: number
  },
  active_run_ids: ID[],
  latest_report_artifact_id: ID | null,
  event_cursor: string
}

export type Message = {
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

export type Source = {
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

export type Citation = {
  source_id: ID,
  locator: string | null,
  excerpt: string | null
}

export type Variable = {
  name: string,
  role: "independent" | "dependent" | "controlled",
  description: string,
  unit: string | null
}

export type Calibration =
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

export type Experiment = {
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

export type Artifact = {
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

export type RunInput =
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

export type RunStatus = "queued" | "running" | "awaiting_approval" |
                 "cancelling" | "succeeded" | "failed" | "cancelled"

export type Run = {
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

export type EvidenceRef = {
  artifact_id: ID,
  frame_index: number | null,
  time_s: number | null,
  row_index: number | null
}

export type Measurement = {
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

export type Claim = {
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

export type RunResults = {
  run_id: ID,
  measurement_count: number,
  claim_ids: ID[],
  chart_artifact_ids: ID[],
  annotated_media_artifact_ids: ID[],
  report_artifact_id: ID | null,
  warnings: { code: string, message: string }[]
}

export type UploadRequest = {
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

export type Upload = {
  id: ID,
  project_id: ID,
  request: UploadRequest,
  status: "pending" | "uploaded" | "completed" | "failed" | "expired",
  artifact_id: ID | null,
  expires_at: Timestamp,
  error: { code: string, message: string } | null
}

export type LogEntry = {
  id: ID,
  run_id: ID,
  sequence: number,
  stream: "stdout" | "stderr" | "system",
  text: string,
  created_at: Timestamp
}

export type Approval = {
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

export type EventPayloads = {
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

export type ProjectEvent = {
  [K in keyof EventPayloads]: {
    cursor: string,
    project_id: ID,
    type: K,
    occurred_at: Timestamp,
    run_id: ID | null,
    payload: EventPayloads[K]
  }
}[keyof EventPayloads]

export type WorkerArtifactRef =
  | { input_artifact_id: ID }
  | { output_artifact_key: string }
export type WorkerEvidence = Omit<EvidenceRef, "artifact_id"> & {
  artifact: WorkerArtifactRef
}
export type WorkerMeasurement = Omit<Measurement,
  "id" | "project_id" | "experiment_id" | "run_id" | "created_at" | "evidence"
> & { local_key: string, evidence: WorkerEvidence[] }
export type WorkerClaim = Omit<Claim,
  "id" | "project_id" | "run_id" | "created_at" | "measurement_ids" | "evidence"
> & {
  local_key: string,
  measurement_keys: string[],
  evidence: WorkerEvidence[]
}
export type WorkerResult = {
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

