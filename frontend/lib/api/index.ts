import type * as T from '@/contracts/api'
import type * as D from '@/contracts/requests'
import { encode, putBytes, request } from './http'
export * from './http'
export type * from '@/contracts/requests'
const projectPath = (p: string) => `/projects/${encode(p)}`
export const resourcePath = (p: string, resource: string, id?: string) => `${projectPath(p)}/${resource}${id === undefined ? '' : `/${encode(id)}`}`
export function queryString(filters: D.ListFilters = {}) {
  const q = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) if (value !== undefined) q.set(key, String(value))
  return q.size ? `?${q}` : ''
}
const get = <T,>(path: string, signal?: AbortSignal) => request<T>(path, { signal })
import type { Page } from '@/contracts/api'
function resources<R>(resource: string) {
  return {
    list: (p: string, filters: D.ListFilters = {}, signal?: AbortSignal) => get<Page<R>>(resourcePath(p, resource) + queryString(filters), signal),
    get: (p: string, id: string, signal?: AbortSignal) => get<R>(resourcePath(p, resource, id), signal),
  }
}
export const api = {
  session: { get: (signal?: AbortSignal) => get<T.Session>('/session', signal) },
  capabilities: { get: (signal?: AbortSignal) => get<T.Capabilities>('/capabilities', signal) },
  projects: {
    list: (filters: D.ListFilters = {}, signal?: AbortSignal) => get<Page<T.Project>>('/projects' + queryString(filters), signal),
    get: (p: string, signal?: AbortSignal) => get<T.Project>(projectPath(p), signal),
    workspace: (p: string, signal?: AbortSignal) => get<T.Workspace>(resourcePath(p, 'workspace'), signal),
    create: (body: D.CreateProject, command: D.CommandOptions) => request<T.Project>('/projects', { method: 'POST', body, command }),
    edit: (p: string, body: D.EditProject, edit: D.EditOptions) => request<T.Project>(projectPath(p), { method: 'PATCH', body, edit }),
  },
  messages: {
    ...resources<T.Message>('messages'),
    create: (p: string, body: D.SubmitMessage, command: D.CommandOptions) => request<{ user_message: T.Message, assistant_message: T.Message, run: T.Run }>(resourcePath(p, 'messages'), { method: 'POST', body, command }),
  },
  sources: { ...resources<T.Source>('sources'), create: (p: string, body: D.CreateSource, command: D.CommandOptions) => request<T.Source>(resourcePath(p, 'sources'), { method: 'POST', body, command }) },
  claims: resources<T.Claim>('claims'),
  experiments: {
    ...resources<T.Experiment>('experiments'),
    create: (p: string, body: D.CreateExperiment, command: D.CommandOptions) => request<T.Experiment>(resourcePath(p, 'experiments'), { method: 'POST', body, command }),
    edit: (p: string, id: string, body: D.EditExperiment, edit: D.EditOptions) => request<T.Experiment>(resourcePath(p, 'experiments', id), { method: 'PATCH', body, edit }),
  },
  uploads: {
    get: (p: string, id: string, options?: AbortSignal | { signal?: AbortSignal }) => get<T.Upload>(resourcePath(p, 'uploads', id), options && 'aborted' in options ? options : options?.signal),
    create: (p: string, body: T.UploadRequest, command: D.CommandOptions) => request<T.Upload>(resourcePath(p, 'uploads'), { method: 'POST', body, command }),
    putContent: (p: string, id: string, blob: Blob, options?: Parameters<typeof putBytes>[2]) => putBytes(resourcePath(p, 'uploads', id) + '/content', blob, options),
    complete: (p: string, id: string, command: D.CommandOptions) => request<T.Artifact>(resourcePath(p, 'uploads', id) + '/complete', { method: 'POST', body: {}, command }),
  },
  artifacts: resources<T.Artifact>('artifacts'),
  runs: {
    ...resources<T.Run>('runs'),
    create: (p: string, body: D.StartRun, command: D.CommandOptions) => request<T.Run>(resourcePath(p, 'runs'), { method: 'POST', body, command }),
    cancel: (p: string, id: string, command: D.CommandOptions) => request<T.Run>(resourcePath(p, 'runs', id) + '/cancel', { method: 'POST', body: {}, command }),
    results: (p: string, id: string, signal?: AbortSignal) => get<T.RunResults>(resourcePath(p, 'runs', id) + '/results', signal),
    measurements: (p: string, id: string, filters: D.ListFilters = {}, signal?: AbortSignal) => get<Page<T.Measurement>>(resourcePath(p, 'runs', id) + '/measurements' + queryString(filters), signal),
    logs: (p: string, id: string, filters: D.ListFilters = {}, signal?: AbortSignal) => get<Page<T.LogEntry>>(resourcePath(p, 'runs', id) + '/logs' + queryString(filters), signal),
  },
  approvals: {
    list: (p: string, run: string, filters: D.ListFilters = {}, signal?: AbortSignal) => get<Page<T.Approval>>(resourcePath(p, 'runs', run) + '/approvals' + queryString(filters), signal),
    decide: (p: string, id: string, body: D.ApprovalDecision, command: D.CommandOptions) => request<T.Approval>(resourcePath(p, 'approvals', id) + '/decision', { method: 'POST', body, command }),
  },
}
export function artifactContentUrl(p: string, id: string, disposition: 'inline' | 'attachment' = 'attachment') {
  return `/api/v1${resourcePath(p, 'artifacts', id)}/content?disposition=${disposition}`
}
