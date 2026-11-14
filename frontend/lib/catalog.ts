'use client'
import { useCallback } from 'react'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient, type InfiniteData, type QueryClient } from '@tanstack/react-query'
import type { CatalogFeatureExtension, CatalogStatus, Collection, CreateCollection, CreateNote, CreateRelation, CreateTag, EditCollection, EditFile, EditTag, FileListFilters, FileOriginType, NoteRevision, Relation, RelationFilters, Tag, WorkspaceFile } from '@/contracts/catalog'
import type { Page } from '@/contracts/api'
import type { ApiResult, CommandOptions, EditOptions } from '@/contracts/requests'
import { encode, request, resourcePath } from '@/lib/api'
import { keys, useCapabilities, useSession } from '@/lib/queries'
import { preferCurrent } from '@/lib/queries/reconcile'

function params(values: Record<string, unknown>) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(values)) {
    if (value === undefined || value === null) continue
    if (Array.isArray(value)) for (const item of value) query.append(key, String(item))
    else query.set(key, String(value))
  }
  return query.size ? `?${query}` : ''
}
const path = (p: string, resource: string, id?: string) => resourcePath(p, resource, id)
const get = <T,>(url: string, signal?: AbortSignal) => request<T>(url, { signal })
const post = <T,>(url: string, body: unknown, command: CommandOptions) => request<T>(url, { method: 'POST', body, command })
const patch = <T,>(url: string, body: unknown, edit: EditOptions) => request<T>(url, { method: 'PATCH', body, edit })
const del = <T = void,>(url: string, edit?: EditOptions) => request<T>(url, { method: 'DELETE', deleteOptions: edit })

/**
 * Canonical file-list filters: artifact kinds deduplicated and sorted (§16.3), an empty kind list removed
 * rather than sent, blank search dropped. Used for both the wire query and the query cache key so that
 * equivalent selections share one cursor sequence.
 */
export function normalizeFileFilters(filters: FileListFilters = {}): FileListFilters {
  const entries = Object.entries(filters).filter(([, value]) => value !== undefined && value !== null && value !== '')
  const out = Object.fromEntries(entries) as FileListFilters
  if (out.q !== undefined) { const q = out.q.trim(); if (q) out.q = q; else delete out.q }
  if (out.artifact_kinds) { const kinds = [...new Set(out.artifact_kinds)].sort(); if (kinds.length) out.artifact_kinds = kinds; else delete out.artifact_kinds }
  if (out.tags && !out.tags.length) delete out.tags
  return out
}
/** Filters that an older backend would silently ignore, so they require `features.workspace_views`. */
export const requiresWorkspaceViews = (filters: FileListFilters) => !!filters.artifact_kinds?.length || filters.origin_id !== undefined

export const catalogApi = {
  files: (p: string, filters: FileListFilters = {}, signal?: AbortSignal) => {
    const { tags, artifact_kinds, ...rest } = normalizeFileFilters(filters)
    return get<Page<WorkspaceFile>>(path(p, 'files') + params({ ...rest, tag: tags, artifact_kind: artifact_kinds }), signal)
  },
  file: (p: string, id: string, signal?: AbortSignal) => get<WorkspaceFile>(path(p, 'files', id), signal),
  contentUrl: (p: string, id: string, revision?: number, disposition: 'inline' | 'attachment' = 'attachment') => `/api/v1${path(p, 'files', id)}/content${params({ ...(revision === undefined ? {} : { revision }), disposition })}`,
  revisions: (p: string, id: string, signal?: AbortSignal, cursor?: string) => get<Page<NoteRevision>>(`${path(p, 'files', id)}/revisions${params({ cursor })}`, signal),
  tags: (p: string, filters: { system?: boolean, cursor?: string, limit?: number } = {}, signal?: AbortSignal) => get<Page<Tag>>(path(p, 'tags') + params(filters), signal),
  tag: (p: string, slug: string, signal?: AbortSignal) => get<Tag>(path(p, 'tags', slug), signal),
  collections: (p: string, filters: { cursor?: string, limit?: number } = {}, signal?: AbortSignal) => get<Page<Collection>>(path(p, 'collections') + params(filters), signal),
  collection: (p: string, id: string, signal?: AbortSignal) => get<Collection>(path(p, 'collections', id), signal),
  relations: (p: string, filters: RelationFilters = {}, signal?: AbortSignal) => get<Page<Relation>>(path(p, 'relations') + params(filters), signal),
  catalog: (p: string, signal?: AbortSignal) => get<CatalogStatus>(path(p, 'catalog'), signal),
  createNote: (p: string, body: CreateNote, command: CommandOptions) => post<WorkspaceFile>(path(p, 'files'), body, command),
  editFile: (p: string, id: string, body: EditFile, edit: EditOptions) => patch<WorkspaceFile>(path(p, 'files', id), body, edit),
  tagFiles: (p: string, body: { file_ids: string[], add?: string[], remove?: string[] }, command: CommandOptions) => post<{ files: WorkspaceFile[] }>(`${path(p, 'files')}/tagging`, body, command),
  createTag: (p: string, body: CreateTag, command: CommandOptions) => post<Tag>(path(p, 'tags'), body, command),
  editTag: (p: string, slug: string, body: EditTag, edit: EditOptions) => patch<Tag>(path(p, 'tags', slug), body, edit),
  deleteTag: (p: string, slug: string, edit: EditOptions) => del(path(p, 'tags', slug), edit),
  createCollection: (p: string, body: CreateCollection, command: CommandOptions) => post<Collection>(path(p, 'collections'), body, command),
  editCollection: (p: string, id: string, body: EditCollection, edit: EditOptions) => patch<Collection>(path(p, 'collections', id), body, edit),
  deleteCollection: (p: string, id: string, edit: EditOptions) => del(path(p, 'collections', id), edit),
  addCollectionFiles: (p: string, id: string, file_ids: string[], command: CommandOptions) => post<{ collection: Collection, added_file_ids: string[] }>(`${path(p, 'collections', id)}/files`, { file_ids }, command),
  removeCollectionFile: (p: string, collectionId: string, fileId: string) => del(`${path(p, 'collections', collectionId)}/files/${encode(fileId)}`),
  createRelation: (p: string, body: CreateRelation, command: CommandOptions) => post<Relation>(path(p, 'relations'), body, command),
  deleteRelation: (p: string, id: string) => del(path(p, 'relations', id)),
}

type CatalogPage<R> = { items: R[], has_next_page: boolean, load_next_page: () => Promise<unknown>, is_loading: boolean, error: Error | null, refetch: () => Promise<unknown>, is_fetching_next_page: boolean }
function rowKey<R>(item: R): string {
  const row = item as Record<string, unknown>
  return String(row.id ?? row.slug ?? row.content_revision ?? row.file_id)
}
function useCatalogList<R extends object>(p: string, resource: string, filters: Record<string, unknown>, load: (cursor: string | undefined, signal: AbortSignal) => Promise<ApiResult<Page<R>>>, enabled = true): CatalogPage<R> {
  const session = useSession()
  const capabilities = useCapabilities()
  const client = useQueryClient()
  const queryKey = ['project', p, `catalog:${resource}`, 'list', filters] as const
  const query = useInfiniteQuery({
    queryKey, initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam, signal }) => {
      const incoming = await load(pageParam, signal)
      const cached = client.getQueryData<InfiniteData<ApiResult<Page<R>>, string | undefined>>(queryKey)
      const existing = new Map(cached?.pages.flatMap(page => page.data.items.map(item => [rowKey(item), item] as const)) ?? [])
      return { ...incoming, data: { ...incoming.data, items: incoming.data.items.map(item => {
        const row = item as Record<string, unknown>
        const detail = typeof row.id === 'string' ? client.getQueryData<ApiResult<R>>(keys.detail(p, `catalog:${resource}`, row.id))?.data : undefined
        return preferCurrent(preferCurrent(existing.get(rowKey(item)), detail ?? item), item)
      }) } }
    }, getNextPageParam: page => page.data.next_cursor ?? undefined,
    enabled: !!p && enabled && !!session.data && !session.error && capabilities.data?.features.workspace_files === true, retry: false,
  })
  const items = new Map<string, R>()
  for (const page of query.data?.pages ?? []) for (const item of page.data.items) {
    const row = item as Record<string, unknown>
    const current = typeof row.id === 'string' ? client.getQueryData<ApiResult<R>>(keys.detail(p, `catalog:${resource}`, row.id))?.data : undefined
    const latest = current && 'revision' in current && 'revision' in row && Number((current as unknown as Record<string, unknown>).revision) > Number(row.revision) ? current : item
    items.set(rowKey(item), latest)
  }
  const { fetchNextPage, refetch: refetchQuery } = query
  const load_next_page = useCallback(() => fetchNextPage(), [fetchNextPage])
  const refetch = useCallback(() => refetchQuery(), [refetchQuery])
  return { items: [...items.values()], has_next_page: !!query.hasNextPage, load_next_page, is_loading: query.isPending, error: query.error, refetch, is_fetching_next_page: query.isFetchingNextPage }
}

/** Catalog capability flags. `views` certifies the complete §16 extension; missing means false. */
export function useCatalogFeatures() {
  const capabilities = useCapabilities()
  const features = capabilities.data?.features as (Record<string, unknown> & CatalogFeatureExtension) | undefined
  return { is_loading: capabilities.is_loading, error: capabilities.error, files: features?.workspace_files === true, views: features?.workspace_views === true, full_text_papers: features?.full_text_papers === true }
}

export function useFiles(p: string, filters: FileListFilters = {}, enabled = true) {
  const features = useCatalogFeatures()
  const normalized = normalizeFileFilters(filters)
  // Never send a views-only filter to a backend that could ignore it and return unrelated files.
  const allowed = enabled && (!requiresWorkspaceViews(normalized) || features.views)
  return useCatalogList(p, 'files', normalized as Record<string, unknown>, (cursor, signal) => catalogApi.files(p, { ...normalized, cursor }, signal), allowed)
}
/** One collection by ID with its ETag, sharing the detail key that list reconciliation reads. */
export function useCollection(p: string, id?: string | null) {
  const session = useSession()
  const features = useCatalogFeatures()
  const query = useQuery({ queryKey: keys.detail(p, 'catalog:collections', id ?? undefined), queryFn: ({ signal }) => catalogApi.collection(p, id!, signal), enabled: !!p && !!id && !!session.data && !session.error && features.files, retry: false })
  const { refetch: refetchQuery } = query
  const refetch = useCallback(() => refetchQuery(), [refetchQuery])
  return { ...query, data: query.data?.data, etag: query.data?.etag ?? null, is_loading: query.isPending, refetch }
}
/**
 * Resolve a scientific origin (`source`, `claim`, `artifact`, …) to its catalog file independently of the
 * current browse filters. With `workspace_views`, one exact `origin_type`+`origin_id` request. Without it,
 * one bounded page of that origin type — never an open-ended page scan. Results are verified client-side.
 */
export function useOriginFile(p: string, type: FileOriginType | null, id: string | null) {
  const session = useSession()
  const features = useCatalogFeatures()
  const exact = features.views
  const filters: FileListFilters = exact ? { origin_type: type ?? undefined, origin_id: id ?? undefined, status: 'all', limit: 2 } : { origin_type: type ?? undefined, status: 'all', limit: 100 }
  const query = useQuery({
    queryKey: ['project', p, 'catalog:files', 'origin', type, id, exact] as const,
    queryFn: ({ signal }) => catalogApi.files(p, filters, signal),
    enabled: !!p && !!type && !!id && !!session.data && !session.error && features.files, retry: false,
  })
  const file = query.data?.data.items.find(f => f.origin?.type === type && f.origin.id === id && f.project_id === p)
  return { file, is_loading: !!type && !!id && query.isPending, error: query.error, missing: !!query.data && !file, bounded: !exact && !!query.data?.data.next_cursor, refetch: query.refetch }
}
export function useFile(p: string, id?: string | null) {
  const session = useSession()
  const capabilities = useCapabilities()
  const client = useQueryClient()
  const queryKey = keys.detail(p, 'catalog:files', id ?? undefined)
  const query = useQuery({ queryKey, queryFn: async ({ signal }) => {
    const incoming = await catalogApi.file(p, id!, signal)
    const current = client.getQueryData<ApiResult<WorkspaceFile>>(queryKey)
    const data = preferCurrent(current?.data, incoming.data)
    return current && data === current.data ? current : { ...incoming, data }
  }, enabled: !!p && !!id && !!session.data && !session.error && capabilities.data?.features.workspace_files === true, retry: false })
  const { refetch: refetchQuery } = query
  const refetch = useCallback(() => refetchQuery(), [refetchQuery])
  return { ...query, data: query.data?.data, etag: query.data?.etag ?? null, request_id: query.data?.request_id ?? null, is_loading: query.isPending, refetch }
}
export function useTags(p: string) { return useCatalogList(p, 'tags', {}, (cursor, signal) => catalogApi.tags(p, { cursor }, signal)) }
export function useCollections(p: string) { return useCatalogList(p, 'collections', {}, (cursor, signal) => catalogApi.collections(p, { cursor }, signal)) }
export function useRelations(p: string, filters: RelationFilters = {}) { return useCatalogList(p, 'relations', filters, (cursor, signal) => catalogApi.relations(p, { ...filters, cursor }, signal)) }
export function useCatalog(p: string) {
  const session = useSession()
  const capabilities = useCapabilities()
  const query = useQuery({ queryKey: keys.detail(p, 'catalog', p), queryFn: ({ signal }) => catalogApi.catalog(p, signal), enabled: !!p && !!session.data && !session.error && capabilities.data?.features.workspace_files === true, retry: false })
  const { refetch: refetchQuery } = query
  const refetch = useCallback(() => refetchQuery(), [refetchQuery])
  return { ...query, data: query.data?.data, etag: query.data?.etag ?? null, is_loading: query.isPending, refetch }
}
export function useNoteRevisions(p: string, id?: string | null) {
  return useCatalogList(p, `file-revisions:${id ?? ''}`, {}, (cursor, signal) => catalogApi.revisions(p, id!, signal, cursor), !!id)
}
export function useCatalogMutation(p: string) {
  const capabilities = useCapabilities()
  const client = useQueryClient()
  const mutation = useMutation({
    mutationFn: (mutateAsync: () => Promise<unknown>) => {
      if (!p || capabilities.data?.features.workspace_files !== true) throw new Error('The project file catalog is not available.')
      return mutateAsync()
    }, retry: false,
    onSuccess: async () => { await invalidateCatalog(client, p) },
  })
  return { ...mutation, error: mutation.error, isPending: mutation.isPending }
}

export async function invalidateCatalog(client: QueryClient, p: string) {
  await client.invalidateQueries({ predicate: query => query.queryKey[0] === 'project' && query.queryKey[1] === p && (query.queryKey[2] === 'catalog' || (typeof query.queryKey[2] === 'string' && query.queryKey[2].startsWith('catalog:'))) })
}
