import type { ArtifactKind, Collection, CollectionPresentation, FileFilter, FileListFilters, FileOriginType, ViewPreset, WorkspaceFile } from '@/contracts/catalog'
import { DEFAULT_COLLECTION_PRESENTATION } from '@/contracts/catalog'

export type SortField = CollectionPresentation['sort']
export type SortOrder = CollectionPresentation['order']
export type StatusFilter = 'active' | 'trashed' | 'all'

export const VIEW_OPTIONS: { id: ViewPreset, label: string }[] = [
  { id: 'desk', label: 'Desk' }, { id: 'literature', label: 'Literature' }, { id: 'notes', label: 'Notes' },
  { id: 'media-data', label: 'Media & data' }, { id: 'findings', label: 'Findings' },
  { id: 'measurements', label: 'Measurements' }, { id: 'all', label: 'All materials' },
]
export const viewLabel = (v: ViewPreset) => VIEW_OPTIONS.find(o => o.id === v)?.label ?? 'Desk'
const VIEWS = new Set<string>(VIEW_OPTIONS.map(v => v.id))
const SORTS = new Set<string>(['created_at', 'updated_at', 'name'])
const ORDERS = new Set<string>(['asc', 'desc'])
const STATUSES = new Set<string>(['active', 'trashed', 'all'])
export const MEDIA_KINDS: ArtifactKind[] = ['dataset', 'image', 'video']
export const PAGE_SIZE = 24

/** Structural constraint contributed by a preset. Authoritative fields only, never tags. */
export function presetConstraint(view: ViewPreset): Pick<FileFilter, 'origin_type' | 'file_kind' | 'artifact_kinds'> {
  switch (view) {
    case 'literature': return { origin_type: 'source' }
    case 'notes': return { file_kind: 'note' }
    case 'media-data': return { artifact_kinds: MEDIA_KINDS }
    case 'findings': return { origin_type: 'claim' }
    case 'measurements': return { origin_type: 'run_measurements' }
    default: return {}
  }
}
/** Whether a file satisfies a preset's structural constraint, using authoritative fields only. */
export function matchesPreset(file: WorkspaceFile, view: ViewPreset) {
  switch (view) {
    case 'literature': return file.origin?.type === 'source'
    case 'notes': return file.file_kind === 'note'
    case 'media-data': return file.origin?.type === 'artifact' && !!file.artifact_kind && MEDIA_KINDS.includes(file.artifact_kind)
    case 'findings': return file.origin?.type === 'claim'
    case 'measurements': return file.origin?.type === 'run_measurements'
    default: return true
  }
}
export const presetDefaultSort = (view: ViewPreset): { sort: SortField, order: SortOrder } => view === 'notes' ? { sort: 'updated_at', order: 'desc' } : { sort: 'created_at', order: 'desc' }
export const resolvedPresentation = (c: Collection | null | undefined): CollectionPresentation => c?.presentation ?? DEFAULT_COLLECTION_PRESENTATION

export type BrowseState = {
  view: ViewPreset, collection: string, q: string, tag: string, file: string,
  sort: SortField, order: SortOrder, status: StatusFilter,
  /** Notices for URL values that were present but invalid. */
  unknownView: boolean, invalid: string[],
  /** Explicit URL values, used to decide whether presentation differs from a collection's saved one. */
  explicit: { view: boolean, sort: boolean, order: boolean },
  origin: { type: Extract<FileOriginType, 'source' | 'claim' | 'artifact'>, id: string } | null,
}

/**
 * URL precedence (spec §5): explicit valid URL values, then the open collection's saved presentation,
 * then the preset default. Unknown view → Desk with a notice. Invalid sort/order/status are reported.
 */
export function parseBrowseState(search: URLSearchParams, collection: Collection | null | undefined): BrowseState {
  const rawView = search.get('view'), rawSort = search.get('sort'), rawOrder = search.get('order'), rawStatus = search.get('status')
  const saved = collection ? resolvedPresentation(collection) : null
  const viewValid = rawView !== null && VIEWS.has(rawView)
  const view: ViewPreset = viewValid ? rawView as ViewPreset : rawView !== null ? 'desk' : saved?.preset ?? 'desk'
  const fallback = saved ? { sort: saved.sort, order: saved.order } : presetDefaultSort(view)
  const sortValid = rawSort !== null && SORTS.has(rawSort), orderValid = rawOrder !== null && ORDERS.has(rawOrder)
  const invalid: string[] = []
  if (rawSort !== null && !sortValid) invalid.push(`sort “${rawSort}”`)
  if (rawOrder !== null && !orderValid) invalid.push(`order “${rawOrder}”`)
  if (rawStatus !== null && !STATUSES.has(rawStatus)) invalid.push(`status “${rawStatus}”`)
  const originType = search.get('source') ? 'source' as const : search.get('claim') ? 'claim' as const : search.get('artifact') ? 'artifact' as const : null
  return {
    view, collection: search.get('collection') ?? '', q: search.get('q') ?? '', tag: search.get('tag') ?? '', file: search.get('file') ?? '',
    sort: sortValid ? rawSort as SortField : fallback.sort, order: orderValid ? rawOrder as SortOrder : fallback.order,
    status: rawStatus !== null && STATUSES.has(rawStatus) ? rawStatus as StatusFilter : collection?.filter?.status ?? 'active',
    unknownView: rawView !== null && !viewValid, invalid,
    explicit: { view: viewValid, sort: sortValid, order: orderValid },
    origin: originType ? { type: originType, id: search.get(originType)! } : null,
  }
}

/** Query for a full view: user constraints + preset constraint, applied by the backend before pagination. */
export function viewFilters(s: Pick<BrowseState, 'view' | 'collection' | 'q' | 'tag' | 'sort' | 'order' | 'status'>, limit = PAGE_SIZE): FileListFilters {
  return { ...presetConstraint(s.view), q: s.q.trim() || undefined, tags: s.tag ? [s.tag] : undefined, collection_id: s.collection || undefined, status: s.status, sort: s.sort, order: s.order, limit }
}

/** Normalized key for project-scoped scroll restoration. Excludes `file`, which only opens the inspector. */
export function browseKey(project_id: string, s: BrowseState) {
  return `stellaris.materials.scroll:${project_id}:${JSON.stringify([s.view, s.collection, s.q.trim(), s.tag, s.sort, s.order, s.status])}`
}

/** Dynamic filter written by Save view: active user constraints plus the preset's structural constraint. */
export function savedViewFilter(s: Pick<BrowseState, 'view' | 'q' | 'tag' | 'status'>): FileFilter {
  const f: FileFilter = { ...presetConstraint(s.view), status: s.status }
  if (s.q.trim()) f.q = s.q.trim()
  if (s.tag) f.tags = [s.tag]
  return f
}

export function describeFilter(f: FileFilter): string {
  const parts: string[] = []
  if (f.origin_type) parts.push(`origin ${f.origin_type.replace('_', ' ')}`)
  if (f.file_kind) parts.push(`${f.file_kind} files`)
  if (f.artifact_kinds?.length) parts.push(`artifact kind ${f.artifact_kinds.join(' or ')}`)
  if (f.q) parts.push(`name contains “${f.q}”`)
  if (f.tags?.length) parts.push(`tagged ${f.tags.join(' and ')}`)
  parts.push(f.status === 'all' ? 'active and trashed' : f.status === 'trashed' ? 'trashed only' : 'active only')
  return parts.join(' · ')
}
