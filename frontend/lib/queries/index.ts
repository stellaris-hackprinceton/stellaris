'use client'

import { useInfiniteQuery, useMutation, useQuery, useQueryClient, type InfiniteData } from '@tanstack/react-query'
import type * as T from '@/contracts/api'
import type * as D from '@/contracts/requests'
import { api, isAuthError, setCsrfToken } from '@/lib/api'
import { preferCurrent } from './reconcile'

export const keys = {
  session: ['session'] as const,
  capabilities: ['capabilities'] as const,
  projects: (filters: D.ListFilters = {}) => ['projects', filters] as const,
  project: (p: string) => ['project', p] as const,
  detail: (p: string, resource: string, id?: string) => ['project', p, resource, 'detail', id ?? ''] as const,
  list: (p: string, resource: string, filters: D.ListFilters = {}) => ['project', p, resource, 'list', filters] as const,
}
export const terminal = (run: T.Run) => ['succeeded', 'failed', 'cancelled'].includes(run.status)
export function useSession() {
  const client = useQueryClient()
  return useQuery<T.Session | null>({ queryKey: keys.session, queryFn: async ({ signal }) => {
    const resolved = (await api.session.get(signal)).data
    const previous = client.getQueryData<T.Session | null>(keys.session)
    if (previous && previous.user.id !== resolved.user.id) {
      await client.cancelQueries({ predicate: q => q.queryKey[0] !== 'session' })
      client.removeQueries({ predicate: q => q.queryKey[0] !== 'session' })
    }
    setCsrfToken(resolved.csrf_token)
    return resolved
  }, retry: false, staleTime: 60000, refetchOnWindowFocus: true })
}
export function useCapabilities() {
  const session = useSession()
  return useQuery({ queryKey: keys.capabilities, queryFn: async ({ signal }) => (await api.capabilities.get(signal)).data, enabled: !!session.data && !session.error, retry: false, staleTime: 60000 })
}
function useDetail<R>(p: string, resource: string, id: string | undefined, load: (signal: AbortSignal) => Promise<D.ApiResult<R>>) {
  const session = useSession()
  const client = useQueryClient(), key = keys.detail(p, resource, id)
  const query = useQuery({ queryKey: key, queryFn: async ({ signal }) => {
    const incoming = await load(signal), current = client.getQueryData<D.ApiResult<R>>(key)
    const data = preferCurrent(current?.data, incoming.data)
    return current && data === current.data ? current : { ...incoming, data }
  }, enabled: !!p && !!id && !!session.data && !session.error, retry: false })
  return { ...query, data: query.data?.data, etag: query.data?.etag ?? null, request_id: query.data?.request_id ?? null }
}
function useList<R extends { id: string }>(key: readonly unknown[], enabled: boolean, load: (cursor: string | undefined, signal: AbortSignal) => Promise<D.ApiResult<T.Page<R>>>) {
  const session = useSession()
  const client = useQueryClient()
  const query = useInfiniteQuery({ queryKey: key, initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam, signal }) => {
      const incoming = await load(pageParam, signal)
      const current = client.getQueryData<CachedPages<R>>(key)
      const existing = new Map(current?.pages.flatMap(page => page.data.items.map(item => [item.id, item] as const)) ?? [])
      return { ...incoming, data: { ...incoming.data, items: incoming.data.items.map(item => {
        const detail = key[0] === 'project' ? client.getQueryData<D.ApiResult<R>>(keys.detail(String(key[1]), String(key[2]), item.id))?.data : undefined
        return preferCurrent(preferCurrent(existing.get(item.id), detail ?? item), item)
      }) } }
    },
    getNextPageParam: result => result.data.next_cursor ?? undefined,
    enabled: enabled && !!session.data && !session.error, retry: false,
  })
  const byId = new Map<string, R>()
  for (const page of query.data?.pages ?? []) for (const item of page.data.items) byId.set(item.id, item)
  return { ...query, items: [...byId.values()], has_next_page: !!query.hasNextPage, load_next_page: query.fetchNextPage }
}
export function useProjects(filters: D.ListFilters = {}) { return useList(keys.projects(filters), true, (cursor, signal) => api.projects.list({ ...filters, cursor }, signal)) }
export function useProject(p: string) { return useDetail(p, 'project', p, signal => api.projects.get(p, signal)) }
export function useWorkspace(p: string) { return useDetail(p, 'workspace', p, signal => api.projects.workspace(p, signal)) }
export function useMessages(p: string) { return useList(keys.list(p, 'messages'), !!p, (cursor, signal) => api.messages.list(p, { cursor }, signal)) }
export function useSources(p: string, f: D.ListFilters = {}) { return useList(keys.list(p, 'sources', f), !!p, (cursor, signal) => api.sources.list(p, { ...f, cursor }, signal)) }
export function useClaims(p: string, f: D.ListFilters = {}) { return useList(keys.list(p, 'claims', f), !!p, (cursor, signal) => api.claims.list(p, { ...f, cursor }, signal)) }
export function useExperiments(p: string) { return useList(keys.list(p, 'experiments'), !!p, (cursor, signal) => api.experiments.list(p, { cursor }, signal)) }
export function useExperiment(p: string, id?: string) { return useDetail(p, 'experiments', id, signal => api.experiments.get(p, id!, signal)) }
export function useArtifact(p: string, id?: string) { return useDetail(p, 'artifacts', id, signal => api.artifacts.get(p, id!, signal)) }
export function useArtifacts(p: string, f: D.ListFilters = {}) { return useList(keys.list(p, 'artifacts', f), !!p, (cursor, signal) => api.artifacts.list(p, { ...f, cursor }, signal)) }
export function useRuns(p: string, f: D.ListFilters = {}) { return useList(keys.list(p, 'runs', f), !!p, (cursor, signal) => api.runs.list(p, { ...f, cursor }, signal)) }
export function useRun(p: string, id?: string) { return useDetail(p, 'runs', id, signal => api.runs.get(p, id!, signal)) }
export function useRunResults(p: string, id?: string) { return useDetail(p, 'results', id, signal => api.runs.results(p, id!, signal)) }
export function useMeasurements(p: string, id: string, f: D.ListFilters = {}) { return useList(keys.list(p, `measurements:${id}`, f), !!p && !!id, (cursor, signal) => api.runs.measurements(p, id, { ...f, cursor }, signal)) }
export function useRunLogs(p: string, id: string) {
  const history = useList(keys.list(p, `logs:${id}`), !!p && !!id, (cursor, signal) => api.runs.logs(p, id, { cursor }, signal))
  // This disabled observer reads a bounded buffer of actual server log events.
  // Historical REST pages remain separate and retain their own cursors.
  const live = useQuery<T.LogEntry[]>({ queryKey: keys.detail(p, 'live-logs', id), enabled: false })
  const entries = new Map(history.items.map(row => [row.sequence, row]))
  for (const entry of live.data ?? []) entries.set(entry.sequence, entry)
  return { ...history, items: [...entries.values()].sort((a, b) => a.sequence - b.sequence) }
}
export function useApprovals(p: string, id: string) { return useList(keys.list(p, `approvals:${id}`), !!p && !!id, (cursor, signal) => api.approvals.list(p, id, { cursor }, signal)) }

export type CreateProjectVariables = { body: D.CreateProject, command: D.CommandOptions }
export type EditProjectVariables = { project_id: string, body: D.EditProject, edit: D.EditOptions }
export type SubmitMessageVariables = { project_id: string, body: D.SubmitMessage, command: D.CommandOptions }
export type CreateSourceVariables = { project_id: string, body: D.CreateSource, command: D.CommandOptions }
export type CreateExperimentVariables = { project_id: string, body: D.CreateExperiment, command: D.CommandOptions }
export type EditExperimentVariables = { project_id: string, experiment_id: string, body: D.EditExperiment, edit: D.EditOptions }
export type StartRunVariables = { project_id: string, body: D.StartRun, command: D.CommandOptions }
export type CancelRunVariables = { project_id: string, run_id: string, command: D.CommandOptions }
export type DecideApprovalVariables = { project_id: string, approval_id: string, body: D.ApprovalDecision, command: D.CommandOptions }
function useCommand<V, R>(fn: (variables: V) => Promise<D.ApiResult<R>>) {
  const client = useQueryClient()
  return useMutation({ mutationFn: fn, retry: false,
    onSuccess: () => { void client.invalidateQueries({ predicate: q => q.queryKey[0] === 'project' || q.queryKey[0] === 'projects' }) },
    onError: error => { if (isAuthError(error)) void client.cancelQueries() },
  })
}
export function useCreateProject() { return useCommand((v: CreateProjectVariables) => api.projects.create(v.body, v.command)) }
export function useEditProject() { return useCommand((v: EditProjectVariables) => api.projects.edit(v.project_id, v.body, v.edit)) }
export function useSubmitMessage() { return useCommand((v: SubmitMessageVariables) => api.messages.create(v.project_id, v.body, v.command)) }
export function useCreateSource() { return useCommand((v: CreateSourceVariables) => api.sources.create(v.project_id, v.body, v.command)) }
export function useCreateExperiment() { return useCommand((v: CreateExperimentVariables) => api.experiments.create(v.project_id, v.body, v.command)) }
export function useEditExperiment() { return useCommand((v: EditExperimentVariables) => api.experiments.edit(v.project_id, v.experiment_id, v.body, v.edit)) }
export function useStartRun() { return useCommand((v: StartRunVariables) => api.runs.create(v.project_id, v.body, v.command)) }
export function useCancelRun() { return useCommand((v: CancelRunVariables) => api.runs.cancel(v.project_id, v.run_id, v.command)) }
export function useDecideApproval() { return useCommand((v: DecideApprovalVariables) => api.approvals.decide(v.project_id, v.approval_id, v.body, v.command)) }
export type CachedPages<R> = InfiniteData<D.ApiResult<T.Page<R>>, string | undefined>
