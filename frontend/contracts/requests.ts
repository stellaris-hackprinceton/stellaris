import type { Experiment, PaperDocumentSelector, PaperMetadata, Project, RunInput } from './api'

export type CreateProject = Pick<Project, 'name'> & Partial<Pick<Project, 'description' | 'research_question'>>
export type EditProject = Partial<Pick<Project, 'name' | 'description' | 'research_question' | 'status'>>
export type CreateExperiment = Omit<Experiment, 'id' | 'project_id' | 'revision' | 'created_at' | 'updated_at'>
export type EditExperiment = Partial<CreateExperiment>
export type SubmitMessage = { content_markdown: string, attachment_ids?: string[], context_artifact_ids?: string[] }
export type CreateSource = { title: string, url: string, authors?: string[], doi?: string | null, published_at?: string | null, abstract?: string | null }
// Only fields the backend accepts. Accepted paper_ingest input can carry backend-authored
// fields (requested_by_run_id) that a new command must not include.
export type PaperIngestRequest = { kind: 'paper_ingest', document: PaperDocumentSelector, metadata?: PaperMetadata | null }
export type StartRun = Exclude<RunInput, { kind: 'agent' } | { kind: 'paper_ingest' }> | PaperIngestRequest
export type ReportRequest = Extract<RunInput, { kind: 'report' }>
export type ApprovalDecision = { decision: 'approve' | 'reject', action_sha256: string }
export type ListFilters = Record<string, string | number | undefined>
export type CommandOptions = { idempotency_key: string, signal?: AbortSignal }
export type EditOptions = { etag: string, signal?: AbortSignal }
export type ApiResult<T> = { data: T, etag: string | null, request_id: string | null }
export type UploadProgress = { loaded_bytes: number, total_bytes: number | null }

// Public request names used by the merged feature modules.
export type CreateProjectRequest = CreateProject
export type EditProjectRequest = EditProject
export type CreateExperimentRequest = CreateExperiment
export type EditExperimentRequest = EditExperiment
export type SubmitMessageRequest = SubmitMessage
export type CreateSourceRequest = CreateSource
