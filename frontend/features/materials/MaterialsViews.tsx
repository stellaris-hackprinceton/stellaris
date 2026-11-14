'use client'
/* eslint-disable @next/next/no-img-element -- Artifact previews require session cookies that the image optimizer cannot forward. */

import Link from 'next/link'
import { useCallback, useEffect, useRef, useState, type ReactNode, type RefObject } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import type { Collection, CollectionPresentation, ViewPreset, WorkspaceFile } from '@/contracts/catalog'
import { catalogApi, invalidateCatalog, useCatalogMutation, useCollection, useCollections, useFile, useFiles, useOriginFile, useTags } from '@/lib/catalog'
import { api, artifactContentUrl } from '@/lib/api'
import { keys, useArtifact, useMeasurements, useProject, useRunResults } from '@/lib/queries'
import { Sheet, newCommandKey } from '@/components/ui'
import { ErrorNotice, projectHref, runHref } from '@/features/execution/feedback'
import { AddSourceDialog } from '@/features/research/canvas/AddSourceDialog'
import { MaterialInspector } from './MaterialInspector'
import { CollectionEditor } from './CollectionEditor'
import { MaterialCard, MeasurementRow, materialTypeLabel } from './MaterialCard'
import { MaterialUpload } from './MaterialUpload'
import { MEDIA_KINDS, VIEW_OPTIONS, browseKey, describeFilter, matchesPreset, parseBrowseState, resolvedPresentation, savedViewFilter, viewFilters, viewLabel, type BrowseState, type SortField, type SortOrder } from './views'
import styles from './materials.module.css'

/**
 * Optional hooks for features owned elsewhere (Chat drafts, paper ingestion, extracted-paper reader).
 * Absent integrations degrade to self-contained behavior; nothing is sent automatically.
 */
export type MaterialsIntegrations = {
  openChat?: (prompt: string) => void,
  addSourceActions?: ReactNode,
  sourceReader?: (props: { project_id: string, source_id: string }) => ReactNode,
}

type Nav = (updates: Record<string, string | null>, mode: 'push' | 'replace') => void
const SORT_OPTIONS: [string, string][] = [['created_at:desc', 'Newest added'], ['created_at:asc', 'Oldest added'], ['updated_at:desc', 'Recently updated'], ['updated_at:asc', 'Least recently updated'], ['name:asc', 'Name A–Z'], ['name:desc', 'Name Z–A']]
const ORIGIN_PARAMS = ['source', 'claim', 'artifact'] as const
const statusOf = (e: unknown) => (e as { status?: number } | null)?.status
const samePresentation = (a: CollectionPresentation, b: CollectionPresentation) => a.preset === b.preset && a.sort === b.sort && a.order === b.order

function stableKey(ref: { current: { key: string, body: string } | null }, body: unknown) {
  const encoded = JSON.stringify(body)
  if (!ref.current || ref.current.body !== encoded) ref.current = { key: newCommandKey(), body: encoded }
  return ref.current.key
}

function useWidth(ref: RefObject<HTMLElement | null>) {
  const [width, setWidth] = useState<number | null>(null)
  useEffect(() => {
    const el = ref.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(entries => setWidth(entries[0]?.contentRect.width ?? null))
    observer.observe(el)
    return () => observer.disconnect()
  }, [ref])
  return width
}

function scrollParent(el: HTMLElement | null): HTMLElement | null {
  for (let node = el?.parentElement ?? null; node; node = node.parentElement) {
    const overflow = getComputedStyle(node).overflowY
    if (overflow === 'auto' || overflow === 'scroll') return node
  }
  return null
}

/**
 * Project-scoped scroll memory keyed by normalized browse state. Saves the first visible card and its offset;
 * restores to it, or to the nearest surviving preceding card, once the list is ready.
 */
function useScrollRestoration(root: RefObject<HTMLElement | null>, key: string, ready: boolean) {
  const restored = useRef<string | null>(null)
  useEffect(() => {
    const el = root.current
    if (!el) return
    const container = scrollParent(el)
    const target: HTMLElement | Window = container ?? window
    let frame = 0
    const save = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        if (restored.current !== key) return
        const top = container ? container.getBoundingClientRect().top : 0
        const cards = [...el.querySelectorAll<HTMLElement>('[data-file-id]')]
        const anchor = cards.find(card => card.getBoundingClientRect().bottom > top)
        if (!anchor) return
        try { sessionStorage.setItem(key, JSON.stringify({ anchor: anchor.dataset.fileId, offset: anchor.getBoundingClientRect().top - top, ids: cards.map(card => card.dataset.fileId) })) } catch { /* Storage can be unavailable; restoration is best-effort. */ }
      })
    }
    target.addEventListener('scroll', save, { passive: true })
    return () => { target.removeEventListener('scroll', save); cancelAnimationFrame(frame) }
  }, [root, key])
  useEffect(() => {
    if (!ready || restored.current === key) return
    restored.current = key
    const el = root.current
    if (!el) return
    let saved: { anchor?: string, offset?: number, ids?: string[] } | null = null
    try { saved = JSON.parse(sessionStorage.getItem(key) ?? 'null') } catch { saved = null }
    if (!saved?.anchor) return
    const order = saved.ids?.length ? saved.ids : [saved.anchor]
    let node: HTMLElement | null = null
    for (let i = Math.max(0, order.indexOf(saved.anchor)); i >= 0 && !node; i--) node = el.querySelector<HTMLElement>(`[data-file-id="${CSS.escape(order[i])}"]`)
    if (!node) return
    const container = scrollParent(el)
    const delta = node.getBoundingClientRect().top - (container ? container.getBoundingClientRect().top : 0) - (saved.offset ?? 0)
    if (container) container.scrollTop += delta; else window.scrollBy(0, delta)
  }, [root, key, ready])
}

export function MaterialsViews({ project_id, integrations = {} }: { project_id: string, integrations?: MaterialsIntegrations }) {
  const search = useSearchParams(), router = useRouter(), client = useQueryClient()
  const project = useProject(project_id)
  const archived = project.data?.status === 'archived'
  const collectionParam = search.get('collection') ?? ''
  const collection = useCollection(project_id, collectionParam || null)
  const state = parseBrowseState(search, collection.data)
  const base = `${projectHref(project_id)}/materials`
  const pageRef = useRef<HTMLElement | null>(null)
  const width = useWidth(pageRef)
  const wide = width === null || width >= 1100, narrowSelect = width !== null && width < 800

  const navigate: Nav = useCallback((updates, mode) => {
    const p = new URLSearchParams(search.toString())
    for (const [k, v] of Object.entries(updates)) { if (v) p.set(k, v); else p.delete(k) }
    const url = `${base}${p.size ? `?${p}` : ''}`
    if (mode === 'push') router.push(url, { scroll: false }); else router.replace(url, { scroll: false })
  }, [search, router, base])

  // Search: 250ms debounce, URL replace (no history entry per character).
  const [qDraft, setQDraft] = useState(state.q), [qSeen, setQSeen] = useState(state.q)
  if (state.q !== qSeen) { setQSeen(state.q); if (state.q.trim() !== qDraft.trim()) setQDraft(state.q) }
  useEffect(() => {
    if (qDraft.trim() === state.q.trim()) return
    const timer = setTimeout(() => navigate({ q: qDraft.trim() || null }, 'replace'), 250)
    return () => clearTimeout(timer)
  }, [qDraft, state.q, navigate])

  const collectionReady = !state.collection || !!collection.data
  const isDesk = state.view === 'desk'
  const list = useFiles(project_id, viewFilters(state), !isDesk && collectionReady)
  const [deskExpanded, setDeskExpanded] = useState(false)
  const recent = useFiles(project_id, viewFilters({ ...state, view: 'desk', sort: 'created_at', order: 'desc' }, deskExpanded ? 13 : 7), isDesk && collectionReady)
  const recentNotes = useFiles(project_id, viewFilters({ ...state, view: 'notes', sort: 'updated_at', order: 'desc' }, 3), isDesk && collectionReady)
  const loaded = isDesk ? [...recent.items.slice(0, deskExpanded ? 12 : 6), ...recentNotes.items.slice(0, 3)] : list.items

  // Deep links resolve by exact origin lookup, independent of the browse filters.
  const origin = useOriginFile(project_id, state.origin?.type ?? null, state.origin?.id ?? null)
  const selectedId = state.file || origin.file?.id || ''
  const linkedOutside = !state.file && !!origin.file && !(matchesPreset(origin.file, state.view) && loaded.some(f => f.id === origin.file!.id))
  const [creatingNote, setCreatingNote] = useState(false), [addingSource, setAddingSource] = useState(false), [savingView, setSavingView] = useState(false)
  const inspectorPushed = useRef(false)

  const inspect = useCallback((id: string) => {
    setCreatingNote(false)
    // The first inspection adds a history entry; switching between inspected items replaces it.
    const push = !state.file && !state.origin
    if (push) inspectorPushed.current = true
    navigate({ file: id, source: null, claim: null, artifact: null }, push ? 'push' : 'replace')
  }, [navigate, state.file, state.origin])
  const closeInspector = () => {
    if (inspectorPushed.current) { inspectorPushed.current = false; router.back(); return }
    navigate({ file: null, source: null, claim: null, artifact: null }, 'replace')
  }
  const selectedFile = useFile(project_id, selectedId || null).data
  const changeView = (view: ViewPreset) => {
    if (view === state.view) return
    // Keep an explicitly linked item; drop a browse selection the new view excludes.
    const keepFile = selectedFile && (state.origin || matchesPreset(selectedFile, view))
    inspectorPushed.current = false
    navigate({ view, sort: null, order: null, ...(keepFile ? {} : { file: null }) }, 'push')
  }
  const openCollection = (id: string) => { inspectorPushed.current = false; navigate({ collection: id, view: null, sort: null, order: null, file: null, ...Object.fromEntries(ORIGIN_PARAMS.map(k => [k, null])) }, 'push') }
  const clearCollection = () => navigate({ collection: null, view: state.view === 'desk' ? null : state.view, sort: state.explicit.sort ? state.sort : null, order: state.explicit.order ? state.order : null }, 'push')
  const clearFilters = () => navigate({ q: null, tag: null, status: null }, 'replace')

  // Focus returns to the originating card when inspection closes (including browser Back).
  const lastSelected = useRef('')
  useEffect(() => {
    const previous = lastSelected.current
    lastSelected.current = selectedId
    if (!selectedId) inspectorPushed.current = false
    if (previous && !selectedId) pageRef.current?.querySelector<HTMLElement>(`[data-file-id="${CSS.escape(previous)}"] button`)?.focus({ preventScroll: true })
  }, [selectedId])
  useScrollRestoration(pageRef, browseKey(project_id, state), collectionReady && (isDesk ? !recent.is_loading : !list.is_loading))

  const tags = useTags(project_id), collections = useCollections(project_id)
  const filtered = !!(state.q.trim() || state.tag || state.status !== 'active')
  const inspectorOpen = !!selectedId || creatingNote
  const panel = creatingNote
    ? <NewNoteForm project_id={project_id} archived={archived} onCancel={() => setCreatingNote(false)} onCreated={id => { setCreatingNote(false); inspect(id) }} />
    : selectedId ? <>
      <InspectorContext project_id={project_id} file_id={selectedId} linkedOutside={linkedOutside} integrations={integrations} />
      <MaterialInspector key={selectedId} project_id={project_id} file_id={selectedId} onClose={wide ? closeInspector : undefined} />
    </> : null

  let content: ReactNode
  if (state.collection && collection.error) {
    content = statusOf(collection.error) === 404
      ? <div className={styles.unavailable} role="alert"><p>This collection is unavailable. It may have been deleted; its materials remain in the project.</p><button type="button" onClick={() => navigate({ collection: null, view: null, sort: null, order: null }, 'push')}>Return to Materials</button></div>
      : <div><ErrorNotice error={collection.error} /><button type="button" onClick={() => void collection.refetch()}>Retry collection</button></div>
  } else if (!collectionReady) content = <p role="status" className={styles.empty}>Loading collection…</p>
  else if (isDesk) content = <DeskView project_id={project_id} recent={recent} notes={recentNotes} expanded={deskExpanded} setExpanded={setDeskExpanded} collections={collections.items} openCollection={openCollection} go={v => changeView(v)} onInspect={inspect} selectedId={selectedId} filtered={filtered} clearFilters={clearFilters} />
  else content = <FullView project_id={project_id} state={state} list={list} onInspect={inspect} onViewAll={() => changeView('all')} openChat={integrations.openChat} selectedId={selectedId} filtered={filtered} clearFilters={clearFilters} archived={archived} collection={collection.data ?? null}
    emptyAction={state.view === 'notes' ? <button type="button" disabled={archived} onClick={() => setCreatingNote(true)}>New note</button> : state.view === 'literature' ? <button type="button" disabled={archived} onClick={() => setAddingSource(true)}>Add source</button> : null} />

  return <section ref={pageRef} className={`${styles.page} ${styles.viewsPage}`}>
    <header className={styles.heading}>
      <div>
        {collection.data ? <><p className={styles.eyebrow}>Materials · Collection</p><h1>{collection.data.name}</h1>{collection.data.description && <p>{collection.data.description}</p>}</> : <h1>Materials</h1>}
        {archived && <p className={styles.notice}>Restore project to add or generate material.</p>}
      </div>
      <div className={styles.actions}>
        <MaterialUpload project_id={project_id} archived={archived} />
        <button type="button" disabled={archived} onClick={() => { setCreatingNote(true) }}>New note</button>
        {(isDesk || state.view === 'literature') && !integrations.addSourceActions && <button type="button" disabled={archived} onClick={() => setAddingSource(true)}>Add source</button>}
        {(isDesk || state.view === 'literature') && integrations.addSourceActions}
        <button type="button" disabled={archived} onClick={() => setSavingView(v => !v)} aria-expanded={savingView}>Save view</button>
      </div>
    </header>

    {narrowSelect
      ? <label className={styles.viewSelect}>View<select value={state.view} onChange={e => changeView(e.target.value as ViewPreset)}>{VIEW_OPTIONS.map(v => <option key={v.id} value={v.id}>{v.label}</option>)}</select></label>
      : <nav aria-label="Materials views" className={styles.viewTabs}>{VIEW_OPTIONS.map(v => <button key={v.id} type="button" aria-current={state.view === v.id ? 'page' : undefined} onClick={() => changeView(v.id)}>{v.label}</button>)}</nav>}
    {state.unknownView && <p className={styles.notice} role="status">Unknown view. Showing Desk.</p>}
    {state.invalid.length > 0 && <p className={styles.notice} role="alert">Unrecognized {state.invalid.join(', ')} in the link. Defaults are shown instead. <button type="button" onClick={() => navigate({ sort: null, order: null, status: null }, 'replace')}>Reset these parameters</button></p>}

    <CollectionsDisclosure project_id={project_id} archived={archived} collections={collections} openCollection={openCollection} activeId={state.collection} />
    {collection.data && <div className={styles.chips}><span className={styles.chip}>Collection: {collection.data.name}{collection.data.filter ? ' · saved filter' : ''}<button type="button" onClick={clearCollection} aria-label={`Clear collection ${collection.data.name}`}>Clear</button></span>
      <PresentationControl project_id={project_id} collection={collection.data} etag={collection.etag} state={state} archived={archived} refetch={collection.refetch} onUseSaved={() => navigate({ view: null, sort: null, order: null }, 'replace')} />
    </div>}

    {savingView && <SaveViewForm project_id={project_id} state={state} archived={archived} inCollection={!!state.collection} onCancel={() => setSavingView(false)} onSaved={id => { setSavingView(false); navigate({ collection: id, view: null, sort: null, order: null, q: null, tag: null, status: null, file: null }, 'push') }} />}

    <div className={styles.toolbar}>
      <label>Search names in this view<input type="search" value={qDraft} onChange={e => setQDraft(e.target.value)} placeholder="Name contains…" /></label>
      <div className={styles.inline}>
        {!isDesk && <label className={styles.sortField}>Sort<select value={`${state.sort}:${state.order}`} onChange={e => { const [sort, order] = e.target.value.split(':') as [SortField, SortOrder]; navigate({ sort, order }, 'replace') }}>{SORT_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>}
        <details className={styles.filters}><summary>Filters{state.tag || state.status !== 'active' ? ' · active' : ''}</summary><div className={styles.filterFields}>
          <label>Tag<select value={state.tag} onChange={e => navigate({ tag: e.target.value || null }, 'replace')}><option value="">All tags</option>{tags.items.map(t => <option key={t.slug} value={t.slug}>{t.label}</option>)}</select></label>
          <label>Show<select value={state.status} onChange={e => navigate({ status: e.target.value }, 'replace')}><option value="active">Active</option><option value="trashed">Trash</option><option value="all">Active + trash</option></select></label>
          {tags.has_next_page && <button type="button" disabled={tags.is_fetching_next_page} onClick={() => void tags.load_next_page()}>Load more tags</button>}
        </div></details>
      </div>
    </div>
    {filtered && <div className={styles.chips}>
      {state.q.trim() && <span className={styles.chip}>Name: {state.q.trim()}<button type="button" aria-label="Remove name search" onClick={() => navigate({ q: null }, 'replace')}>×</button></span>}
      {state.tag && <span className={styles.chip}>Tag: {tags.items.find(t => t.slug === state.tag)?.label ?? state.tag}<button type="button" aria-label="Remove tag filter" onClick={() => navigate({ tag: null }, 'replace')}>×</button></span>}
      {state.status !== 'active' && <span className={styles.chip}>{state.status === 'all' ? 'Including trash' : 'Trash'}<button type="button" aria-label="Remove status filter" onClick={() => navigate({ status: null }, 'replace')}>×</button></span>}
      <button type="button" onClick={clearFilters}>Clear filters</button>
    </div>}

    {state.origin && !selectedId && <div role="status" className={styles.notice}>
      {origin.is_loading ? `Finding the linked ${state.origin.type}…` : origin.error ? <>The linked {state.origin.type} could not be resolved. <button type="button" onClick={() => void origin.refetch()}>Retry</button></> : origin.missing ? <>{origin.bounded ? `The linked ${state.origin.type} was not found in the checked page. This backend cannot resolve it directly.` : `The linked ${state.origin.type} is not in this project’s catalog.`} <button type="button" onClick={closeInspector}>Dismiss</button></> : null}
    </div>}

    <div className={wide && inspectorOpen ? styles.browseWithInspector : styles.browse}>
      <div className={styles.browseMain}>{content}</div>
      {wide && inspectorOpen && <aside className={styles.inspectorColumn}>{creatingNote ? <section className={styles.inspector}>{panel}</section> : panel}</aside>}
    </div>
    {!wide && <Sheet open={inspectorOpen} onClose={() => creatingNote ? setCreatingNote(false) : closeInspector()} title={creatingNote ? 'New note' : 'Material details'}>{panel}</Sheet>}

    <AddSourceDialog project_id={project_id} open={addingSource} onClose={() => setAddingSource(false)} onCreated={() => { setAddingSource(false); void invalidateCatalog(client, project_id) }} />
  </section>
}

type FileList = ReturnType<typeof useFiles>

function CountLabel({ list }: { list: FileList }) {
  if (list.is_loading) return null
  return <span className={styles.meta}>{list.has_next_page ? `${list.items.length} loaded · more available` : `${list.items.length} item${list.items.length === 1 ? '' : 's'}`}</span>
}
function LoadMore({ list }: { list: FileList }) {
  if (!list.has_next_page) return null
  return <div className={styles.loadMore}><button type="button" disabled={list.is_fetching_next_page} onClick={() => void list.load_next_page().catch(() => {})}>{list.is_fetching_next_page ? 'Loading…' : 'Load more'}</button></div>
}
function ListError({ list }: { list: FileList }) {
  if (!list.error) return null
  return <div><ErrorNotice error={list.error} /><button type="button" onClick={() => void (list.items.length ? list.load_next_page() : list.refetch()).catch(() => {})}>Retry</button></div>
}

function DeskView({ project_id, recent, notes, expanded, setExpanded, collections, openCollection, go, onInspect, selectedId, filtered, clearFilters }: {
  project_id: string, recent: FileList, notes: FileList, expanded: boolean, setExpanded: (v: boolean) => void, collections: Collection[],
  openCollection: (id: string) => void, go: (v: ViewPreset) => void, onInspect: (id: string) => void, selectedId: string, filtered: boolean, clearFilters: () => void,
}) {
  const shown = recent.items.slice(0, expanded ? 12 : 6)
  const named = [...collections].sort((a, b) => a.name.localeCompare(b.name)).slice(0, 6)
  return <div className={styles.desk}>
    <section className={styles.widget} aria-labelledby="desk-recent">
      <header className={styles.widgetHeader}><h2 id="desk-recent">Recently added</h2></header>
      {recent.is_loading ? <p role="status" className={styles.empty}>Loading materials…</p> : recent.error ? <ListError list={recent} /> : !shown.length
        ? <p className={styles.empty}>{filtered ? <>No materials match these filters. <button type="button" onClick={clearFilters}>Clear filters</button></> : 'Nothing has been added yet. Add a source, create a note, or upload a file to Materials.'}</p>
        : <div className={styles.cardGrid}>{shown.map(f => <MaterialCard key={f.id} project_id={project_id} file={f} onInspect={onInspect} selected={selectedId === f.id} />)}</div>}
      {(expanded || recent.items.length > 6) && <div className={styles.widgetFooter}><button type="button" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? 'Collapse' : 'Expand'}</button><button type="button" onClick={() => go('all')}>View all</button></div>}
    </section>
    <div className={styles.deskColumns}>
      <section className={styles.widget} aria-labelledby="desk-notes">
        <header className={styles.widgetHeader}><h2 id="desk-notes">Recent notes</h2></header>
        {notes.is_loading ? <p role="status" className={styles.empty}>Loading notes…</p> : notes.error ? <ListError list={notes} /> : !notes.items.length
          ? <p className={styles.empty}>{filtered ? 'No notes match these filters.' : 'No notes yet. Use New note to write one.'}</p>
          : <div className={styles.stack}>{notes.items.slice(0, 3).map(f => <MaterialCard key={f.id} project_id={project_id} file={f} onInspect={onInspect} selected={selectedId === f.id} />)}</div>}
        <div className={styles.widgetFooter}><button type="button" onClick={() => go('notes')}>View all notes</button></div>
      </section>
      <section className={styles.widget} aria-labelledby="desk-collections">
        <header className={styles.widgetHeader}><h2 id="desk-collections">Collections</h2></header>
        <p className={styles.meta}>Shortcuts to saved organization. These are navigation links, not matching materials.</p>
        {named.length ? <ul className={styles.shortcutList}>{named.map(c => <li key={c.id}><button type="button" onClick={() => openCollection(c.id)}>{c.name}</button> <span className={styles.meta}>{c.filter ? 'saved filter' : 'explicit membership'}</span></li>)}</ul> : <p className={styles.empty}>No collections yet. Save a view or create one under Collections.</p>}
      </section>
    </div>
    <nav aria-label="Material shortcuts" className={styles.shortcutRow}>
      <button type="button" onClick={() => go('literature')}>Literature</button>
      <button type="button" onClick={() => go('media-data')}>Media &amp; data</button>
      <button type="button" onClick={() => go('findings')}>Findings</button>
      <button type="button" onClick={() => go('measurements')}>Measurements</button>
      <Link href={`${projectHref(project_id)}/reports`}>Reports</Link>
      <button type="button" onClick={() => go('all')}>All materials</button>
    </nav>
  </div>
}

const EMPTY_VIEW: Record<ViewPreset, string> = {
  desk: '', literature: 'No sources saved yet. Add a reference or find literature in Chat.', notes: 'No notes yet. Notes organize your thinking; they are not scientific evidence.',
  'media-data': 'No images, videos, or datasets yet. Upload a file to Materials.', findings: 'Findings appear when research or analysis saves a claim.',
  measurements: 'Analyze an experiment to save measurements.', all: 'No materials yet.',
}

function FullView({ project_id, state, list, onInspect, onViewAll, openChat, selectedId, filtered, clearFilters, archived, collection, emptyAction }: {
  project_id: string, state: BrowseState, list: FileList, onInspect: (id: string) => void, onViewAll: () => void, openChat?: (prompt: string) => void, selectedId: string, filtered: boolean,
  clearFilters: () => void, archived: boolean, collection: Collection | null, emptyAction: ReactNode,
}) {
  const narrowsExplicit = !!collection && !collection.filter && state.view !== 'all'
  let body: ReactNode
  if (list.is_loading) body = <p role="status" className={styles.empty}>Loading {viewLabel(state.view).toLowerCase()}…</p>
  else if (!list.items.length && list.error) body = <ListError list={list} />
  else if (!list.items.length) body = <div className={styles.empty}>{filtered ? <p>No materials match these filters. <button type="button" onClick={clearFilters}>Clear filters</button></p> : collection ? <p>{narrowsExplicit ? <>This presentation shows matching members. <button type="button" onClick={onViewAll}>Open All materials</button> to see the collection&apos;s other items.</> : 'This collection has no matching materials.'}</p> : <><p>{EMPTY_VIEW[state.view]}</p>{emptyAction}</>}</div>
  else if (state.view === 'all') body = <AllList project_id={project_id} list={list} onInspect={onInspect} selectedId={selectedId} archived={archived} />
  else if (state.view === 'measurements') body = <MeasurementGroups project_id={project_id} items={list.items} onInspect={onInspect} selectedId={selectedId} />
  else body = <div className={styles.cardGrid}>{list.items.map(f => <MaterialCard key={f.id} project_id={project_id} file={f} onInspect={onInspect} selected={selectedId === f.id} />)}</div>
  return <section className={styles.widget} aria-labelledby="view-heading">
    <header className={styles.widgetHeader}><h2 id="view-heading">{viewLabel(state.view)}</h2><CountLabel list={list} /></header>
    {narrowsExplicit && <p className={styles.notice}>This presentation shows matching members. Open All materials to see the collection&apos;s other items.</p>}
    {state.view === 'literature' && <ChatPrompt label="Find literature in Chat" initial="Find published literature relevant to this project's research question." openChat={openChat} />}
    {body}
    {list.items.length > 0 && <ListError list={list} />}
    <LoadMore list={list} />
  </section>
}

function MeasurementGroups({ project_id, items, onInspect, selectedId }: { project_id: string, items: WorkspaceFile[], onInspect: (id: string) => void, selectedId: string }) {
  const runs = useQueries({ queries: items.map(f => ({ queryKey: keys.detail(project_id, 'runs', f.origin?.id), queryFn: ({ signal }: { signal: AbortSignal }) => api.runs.get(project_id, f.origin!.id, signal), enabled: !!f.origin, retry: false })) })
  const experimentOf = (i: number) => { const input = runs[i]?.data?.data.input; return input?.kind === 'analysis' ? input.experiment_id : null }
  const experimentIds = [...new Set(items.map((_, i) => experimentOf(i)).filter((x): x is string => !!x))]
  const experiments = useQueries({ queries: experimentIds.map(id => ({ queryKey: keys.detail(project_id, 'experiments', id), queryFn: ({ signal }: { signal: AbortSignal }) => api.experiments.get(project_id, id, signal), retry: false })) })
  const titles = new Map(experimentIds.map((id, i) => [id, experiments[i]?.data?.data.title]))
  const groups = new Map<string, WorkspaceFile[]>()
  items.forEach((f, i) => {
    const key = experimentOf(i) ?? (runs[i]?.isPending ? '…pending' : '…none')
    groups.set(key, [...(groups.get(key) ?? []), f])
  })
  return <>
    <p className={styles.meta}>Grouping loaded results by experiment. Groups may extend as more pages load; they are not complete histories.</p>
    {[...groups.entries()].map(([key, files]) => <section key={key} className={styles.group} aria-label={key}>
      <h3>{key === '…pending' ? 'Resolving experiment…' : key === '…none' ? 'No experiment recorded' : titles.get(key) ?? 'Experiment'}</h3>
      <div className={styles.cardGrid}>{files.map(f => <MaterialCard key={f.id} project_id={project_id} file={f} onInspect={onInspect} selected={selectedId === f.id} />)}</div>
    </section>)}
  </>
}

function AllList({ project_id, list, onInspect, selectedId, archived }: { project_id: string, list: FileList, onInspect: (id: string) => void, selectedId: string, archived: boolean }) {
  const mutation = useCatalogMutation(project_id), tags = useTags(project_id), collections = useCollections(project_id)
  const [selectedIds, setSelectedIds] = useState<string[]>([]), [bulkTag, setBulkTag] = useState(''), [target, setTarget] = useState('')
  const tagCommand = useRef<{ key: string, body: string } | null>(null), memberCommand = useRef<{ key: string, body: string } | null>(null)
  const protectedSelection = list.items.some(f => selectedIds.includes(f.id) && f.tags.some(t => t.slug === bulkTag && t.assigned_by === 'system'))
  const toggle = (id: string) => setSelectedIds(v => v.includes(id) ? v.filter(x => x !== id) : [...v, id])
  const bulkTagging = async (add: boolean) => {
    if (!selectedIds.length || !bulkTag) return
    const body = { file_ids: selectedIds, ...(add ? { add: [bulkTag] } : { remove: [bulkTag] }) }
    const key = stableKey(tagCommand, body)
    try { await mutation.mutateAsync(() => catalogApi.tagFiles(project_id, body, { idempotency_key: key })); tagCommand.current = null; setSelectedIds([]) } catch { /* Error stays visible; retry reuses the key. */ }
  }
  const addMembers = async () => {
    if (!selectedIds.length || !target) return
    const key = stableKey(memberCommand, { target, file_ids: selectedIds })
    try { await mutation.mutateAsync(() => catalogApi.addCollectionFiles(project_id, target, selectedIds, { idempotency_key: key })); memberCommand.current = null; setSelectedIds([]) } catch { /* Error stays visible; retry reuses the key. */ }
  }
  const explicit = collections.items.filter(c => !c.filter)
  return <>
    {selectedIds.length > 0 && <div className={styles.bulkBar} role="group" aria-label="Selected materials">
      <span>{selectedIds.length} selected</span>
      <select aria-label="Bulk tag" value={bulkTag} onChange={e => setBulkTag(e.target.value)}><option value="">Choose tag</option>{tags.items.map(t => <option key={t.slug} value={t.slug}>{t.label}</option>)}</select>
      <button type="button" disabled={!bulkTag || archived || mutation.isPending} onClick={() => void bulkTagging(true)}>Add tag</button>
      <button type="button" disabled={!bulkTag || archived || protectedSelection || mutation.isPending} title={protectedSelection ? 'Recorded tag assignments cannot be removed' : undefined} onClick={() => void bulkTagging(false)}>Remove tag</button>
      <select aria-label="Add selection to collection" value={target} onChange={e => setTarget(e.target.value)}><option value="">Explicit collection</option>{explicit.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
      <button type="button" disabled={!target || archived || mutation.isPending} onClick={() => void addMembers()}>Add to collection</button>
      <button type="button" onClick={() => setSelectedIds([])}>Clear selection</button>
    </div>}
    <ErrorNotice error={mutation.error} />
    <ul className={styles.items}>{list.items.map(f => <li key={f.id} className={styles.itemWrap} data-file-id={f.id}>
      <button className={styles.item} type="button" aria-current={selectedId === f.id ? 'true' : undefined} onClick={() => onInspect(f.id)}>
        <span className={styles.itemName}>{f.name}</span>
        <span className={styles.meta}>{materialTypeLabel(f)} · {f.scientific_origin ?? (f.file_kind === 'note' ? 'user note' : 'no scientific origin')} · {new Date(f.created_at).toLocaleDateString()}{f.status === 'trashed' ? ' · in trash' : ''}</span>
        {f.tags.length > 0 && <span className={styles.tags}>{f.tags.map(t => <span className={styles.tag} key={t.slug}>{t.slug}</span>)}</span>}
      </button>
      <label className={styles.select}><input type="checkbox" checked={selectedIds.includes(f.id)} onChange={() => toggle(f.id)} aria-label={`Select ${f.name}`} /> Select</label>
    </li>)}</ul>
    <TagTools project_id={project_id} archived={archived} />
  </>
}

function TagTools({ project_id, archived }: { project_id: string, archived: boolean }) {
  const tags = useTags(project_id), mutation = useCatalogMutation(project_id)
  const [slug, setSlug] = useState(''), [label, setLabel] = useState('')
  const command = useRef<{ key: string, body: string } | null>(null)
  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!slug.trim()) return
    const body = { slug: slug.trim().toLowerCase().replace(/\s+/g, '-'), label: label.trim() || slug.trim() }
    const key = stableKey(command, body)
    try { await mutation.mutateAsync(() => catalogApi.createTag(project_id, body, { idempotency_key: key })); command.current = null; setSlug(''); setLabel('') } catch { /* Retry uses the same key. */ }
  }
  return <details className={styles.tools}><summary>Manage tags</summary>
    <form className={styles.inline} onSubmit={e => void create(e)}><input aria-label="Tag slug" value={slug} onChange={e => setSlug(e.target.value)} placeholder="new-tag" /><input aria-label="Tag label" value={label} onChange={e => setLabel(e.target.value)} placeholder="Display label" /><button disabled={archived || mutation.isPending}>Create tag</button></form>
    <ul className={styles.plainList}>{tags.items.map(t => <li key={t.slug}>{t.label} · {t.file_count} files{t.system ? ' · default tag' : ''}
      <details><summary>Edit label and color</summary><form className={styles.inline} onSubmit={e => { e.preventDefault(); const fd = new FormData(e.currentTarget); void mutation.mutateAsync(() => catalogApi.editTag(project_id, t.slug, { label: String(fd.get('label')), color: String(fd.get('color')) || null }, { etag: `"${t.revision}"` })).catch(() => {}) }}><input name="label" aria-label={`Label for ${t.slug}`} defaultValue={t.label} /><input name="color" type="color" aria-label={`Color for ${t.slug}`} defaultValue={t.color ?? '#758393'} /><button disabled={archived}>Save</button></form></details>
      {!t.system && <button type="button" disabled={archived} onClick={() => { if (window.confirm(`Delete tag “${t.label}” and remove its user assignments?`)) void mutation.mutateAsync(() => catalogApi.deleteTag(project_id, t.slug, { etag: `"${t.revision}"` })).catch(() => {}) }}>Delete</button>}
    </li>)}</ul>
    {tags.has_next_page && <button type="button" disabled={tags.is_fetching_next_page} onClick={() => void tags.load_next_page()}>Load more tags</button>}
    <ErrorNotice error={mutation.error ?? tags.error} />
  </details>
}

function CollectionsDisclosure({ project_id, archived, collections, openCollection, activeId }: { project_id: string, archived: boolean, collections: ReturnType<typeof useCollections>, openCollection: (id: string) => void, activeId: string }) {
  const mutation = useCatalogMutation(project_id)
  const [name, setName] = useState(''), [description, setDescription] = useState('')
  const command = useRef<{ key: string, body: string } | null>(null)
  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    const body = { name: name.trim(), description: description.trim(), filter: null }
    const key = stableKey(command, body)
    try { const r = await mutation.mutateAsync(() => catalogApi.createCollection(project_id, body, { idempotency_key: key })) as { data?: Collection }; command.current = null; setName(''); setDescription(''); if (r?.data) openCollection(r.data.id) } catch { /* Form and key retained for retry. */ }
  }
  return <details className={styles.collections}><summary>Collections{collections.items.length ? ` (${collections.items.length}${collections.has_next_page ? '+' : ''})` : ''}</summary>
    <ul className={styles.plainList}>{collections.items.map(c => <li key={c.id}>
      <button type="button" aria-current={activeId === c.id ? 'true' : undefined} onClick={() => openCollection(c.id)}>{c.name}</button> <span className={styles.meta}>{c.filter ? `saved filter: ${describeFilter(c.filter)}` : 'explicit membership'}</span>
      <CollectionEditor project_id={project_id} collection={c} archived={archived} />
      <button type="button" disabled={archived} onClick={() => { if (window.confirm(`Delete collection “${c.name}”? This removes its organization and saved presentation. Its materials stay in the project.`)) void mutation.mutateAsync(() => catalogApi.deleteCollection(project_id, c.id, { etag: `"${c.revision}"` })).catch(() => {}) }}>Delete collection</button>
    </li>)}</ul>
    {collections.has_next_page && <button type="button" disabled={collections.is_fetching_next_page} onClick={() => void collections.load_next_page()}>Load more collections</button>}
    <form className={styles.form} onSubmit={e => void create(e)}><h3>New collection</h3><p className={styles.meta}>Creates an explicit collection. Add members from All materials. Use Save view for a dynamic filter.</p>
      <label>Collection name<input value={name} onChange={e => setName(e.target.value)} maxLength={120} /></label>
      <label>Description<input value={description} onChange={e => setDescription(e.target.value)} maxLength={2000} /></label>
      <button disabled={archived || mutation.isPending || !name.trim()}>Create collection</button></form>
    <ErrorNotice error={mutation.error ?? collections.error} />
  </details>
}

function SaveViewForm({ project_id, state, archived, inCollection, onCancel, onSaved }: { project_id: string, state: BrowseState, archived: boolean, inCollection: boolean, onCancel: () => void, onSaved: (id: string) => void }) {
  const mutation = useCatalogMutation(project_id)
  const [name, setName] = useState(''), [description, setDescription] = useState(''), [preset, setPreset] = useState<ViewPreset>(state.view)
  const command = useRef<{ key: string, body: string } | null>(null)
  const filter = savedViewFilter({ ...state, view: preset })
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim() || archived) return
    const body = { name: name.trim(), description: description.trim(), filter, presentation: { preset, sort: state.sort, order: state.order } }
    const key = stableKey(command, body)
    try { const r = await mutation.mutateAsync(() => catalogApi.createCollection(project_id, body, { idempotency_key: key })) as { data?: Collection }; command.current = null; if (r?.data) onSaved(r.data.id) } catch { /* Keep the form and command identity for an unchanged retry. */ }
  }
  return <form className={`${styles.form} ${styles.saveView}`} onSubmit={e => void submit(e)} aria-label="Save view">
    <h2>Save view</h2>
    <p className={styles.meta}>Saves a dynamic collection. Membership filter: {describeFilter(filter)}.{inCollection ? ' The open collection’s membership is not part of this filter.' : ''} Changing its presentation later does not change this filter.</p>
    <label>Name<input value={name} onChange={e => setName(e.target.value)} maxLength={120} required /></label>
    <label>Description<input value={description} onChange={e => setDescription(e.target.value)} maxLength={2000} /></label>
    <label>Presentation<select value={preset} onChange={e => setPreset(e.target.value as ViewPreset)}>{VIEW_OPTIONS.map(v => <option key={v.id} value={v.id}>{v.label}</option>)}</select></label>
    <p className={styles.meta}>Order: {SORT_OPTIONS.find(([v]) => v === `${state.sort}:${state.order}`)?.[1]}</p>
    <div className={styles.actions}><button disabled={archived || mutation.isPending || !name.trim()}>Save view</button><button type="button" onClick={onCancel}>Cancel</button></div>
    <ErrorNotice error={mutation.error} />
  </form>
}

function PresentationControl({ project_id, collection, etag, state, archived, refetch, onUseSaved }: { project_id: string, collection: Collection, etag: string | null, state: BrowseState, archived: boolean, refetch: () => Promise<unknown>, onUseSaved: () => void }) {
  const mutation = useCatalogMutation(project_id)
  const [conflict, setConflict] = useState(false)
  const mine: CollectionPresentation = { preset: state.view, sort: state.sort, order: state.order }
  const saved = resolvedPresentation(collection)
  const differs = !samePresentation(mine, saved)
  if (!differs) return null
  const save = async () => {
    try { await mutation.mutateAsync(() => catalogApi.editCollection(project_id, collection.id, { presentation: mine }, { etag: etag ?? `"${collection.revision}"` })); setConflict(false) }
    catch (e) { if (statusOf(e) === 412) { setConflict(true); await refetch().catch(() => {}) } }
  }
  const describe = (p: CollectionPresentation) => `${viewLabel(p.preset)} · ${SORT_OPTIONS.find(([v]) => v === `${p.sort}:${p.order}`)?.[1] ?? `${p.sort} ${p.order}`}`
  return <>
    {!conflict && <button type="button" disabled={archived || mutation.isPending} onClick={() => void save()}>Save presentation</button>}
    {conflict && <div className={styles.conflict} role="alert"><p>This collection&apos;s saved presentation changed while you were browsing. It is now <strong>{describe(saved)}</strong>. Your unsaved presentation (<strong>{describe(mine)}</strong>) is still shown.</p>
      <div className={styles.actions}><button type="button" onClick={() => { setConflict(false); mutation.reset(); onUseSaved() }}>Use saved</button><button type="button" disabled={archived || mutation.isPending} onClick={() => void save()}>Retry my presentation</button></div></div>}
    {!conflict && statusOf(mutation.error) !== 412 && <ErrorNotice error={mutation.error} />}
  </>
}

function NewNoteForm({ project_id, archived, onCancel, onCreated }: { project_id: string, archived: boolean, onCancel: () => void, onCreated: (id: string) => void }) {
  const mutation = useCatalogMutation(project_id)
  const [name, setName] = useState(''), [content, setContent] = useState(''), [mime, setMime] = useState<'text/markdown' | 'text/plain'>('text/markdown')
  const command = useRef<{ key: string, body: string } | null>(null)
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (archived || !name.trim()) return
    const body = { name: name.trim(), content, mime_type: mime }
    const key = stableKey(command, body)
    try { const r = await mutation.mutateAsync(() => catalogApi.createNote(project_id, body, { idempotency_key: key })) as { data?: WorkspaceFile }; command.current = null; if (r?.data) onCreated(r.data.id); else onCancel() } catch { /* Keep the draft and command key for a safe retry. */ }
  }
  return <form className={`${styles.form} ${styles.body}`} onSubmit={e => void submit(e)} aria-label="New note">
    <p className={styles.notice}>User note · organizational content only. Notes are not scientific evidence.</p>
    <label>Title<input value={name} onChange={e => setName(e.target.value)} placeholder="Research note.md" required /></label>
    <label>Format<select value={mime} onChange={e => setMime(e.target.value as typeof mime)}><option value="text/markdown">Markdown</option><option value="text/plain">Plain text</option></select></label>
    <label>Content<textarea className={styles.editor} value={content} onChange={e => setContent(e.target.value)} rows={8} /></label>
    <div className={styles.actions}><button disabled={!name.trim() || archived || mutation.isPending}>Create note</button><button type="button" onClick={onCancel}>Cancel</button></div>
    <ErrorNotice error={mutation.error} />
  </form>
}

function ChatPrompt({ label, initial, openChat }: { label: string, initial: string, openChat?: (prompt: string) => void }) {
  const [text, setText] = useState(initial), [copied, setCopied] = useState(false)
  return <details className={styles.tools}><summary>{label}</summary>
    <label className={styles.form}>Prompt (editable; nothing is sent automatically)<textarea value={text} onChange={e => { setText(e.target.value); setCopied(false) }} rows={3} /></label>
    <div className={styles.actions}>{openChat ? <button type="button" onClick={() => openChat(text)}>Open in Chat</button> : <button type="button" onClick={() => void navigator.clipboard?.writeText(text).then(() => setCopied(true)).catch(() => {})}>Copy prompt</button>}{copied && <span role="status" className={styles.meta}>Copied. Paste it into Research chat to continue.</span>}</div>
  </details>
}

function InspectorContext({ project_id, file_id, linkedOutside, integrations }: { project_id: string, file_id: string, linkedOutside: boolean, integrations: MaterialsIntegrations }) {
  const file = useFile(project_id, file_id).data
  const origin = file?.origin
  return <>
    {linkedOutside && <p className={styles.notice} role="status">Opened from a link. This item is outside the current view.</p>}
    {file && origin?.type === 'source' && <SourceCitation project_id={project_id} source_id={origin.id} integrations={integrations} />}
    {file && origin?.type === 'claim' && <div className={styles.contextBox}><ChatPrompt label="Continue research in Chat" initial={`Continue research on the recorded finding “${file.name}”. What evidence would strengthen or challenge it?`} openChat={integrations.openChat} /></div>}
    {file && origin?.type === 'artifact' && file.artifact_kind && MEDIA_KINDS.includes(file.artifact_kind) && <MediaActions project_id={project_id} artifact_id={origin.id} />}
    {file && origin?.type === 'run_measurements' && <MeasurementDetails project_id={project_id} file={file} run_id={origin.id} />}
  </>
}

function SourceCitation({ project_id, source_id, integrations }: { project_id: string, source_id: string, integrations: MaterialsIntegrations }) {
  const q = useQuery({ queryKey: keys.detail(project_id, 'sources', source_id), queryFn: ({ signal }) => api.sources.get(project_id, source_id, signal), enabled: !integrations.sourceReader, retry: false })
  if (integrations.sourceReader) return <div className={styles.contextBox}>{integrations.sourceReader({ project_id, source_id })}</div>
  if (q.isPending) return <p className={styles.contextBox} role="status">Loading citation…</p>
  if (q.error) return <div className={styles.contextBox}><ErrorNotice error={q.error} /><button type="button" onClick={() => void q.refetch()}>Retry</button></div>
  const s = q.data.data
  return <div className={styles.contextBox}><h3>Citation</h3><dl className={styles.dl}>
    <dt>Authors</dt><dd>{s.authors.length ? s.authors.join(', ') : 'Not recorded'}</dd>
    {s.published_at && <><dt>Published</dt><dd>{s.published_at}</dd></>}
    {s.doi && <><dt>DOI</dt><dd><a href={`https://doi.org/${encodeURIComponent(s.doi)}`} target="_blank" rel="noreferrer">{s.doi}</a></dd></>}
    <dt>Provider</dt><dd>{s.provider}{s.external_id ? ` · ${s.external_id}` : ''}</dd>
    <dt>Retrieval</dt><dd>{s.retrieval_status.replace(/_/g, ' ')} · {new Date(s.retrieved_at).toLocaleString()}</dd>
    {/^https?:\/\//i.test(s.url) && <><dt>Link</dt><dd><a href={s.url} target="_blank" rel="noreferrer">Open source page</a></dd></>}
    <dt>Document</dt><dd>{s.document_artifact_id ? <Link href={`${projectHref(project_id)}/materials?artifact=${encodeURIComponent(s.document_artifact_id)}`}>Open saved document</Link> : 'No document saved'}</dd>
  </dl></div>
}

function MediaActions({ project_id, artifact_id }: { project_id: string, artifact_id: string }) {
  const a = useArtifact(project_id, artifact_id)
  const studio = `${projectHref(project_id)}/studio`
  return <div className={`${styles.contextBox} ${styles.actions}`}>
    {a.data?.experiment_id ? <Link href={`${studio}?experiment=${encodeURIComponent(a.data.experiment_id)}&view=inputs`}>Open in Experiment Studio</Link> : a.data ? <span className={styles.meta}>No recorded experiment association.</span> : null}
  </div>
}

function GalleryItem({ project_id, id }: { project_id: string, id: string }) {
  const a = useArtifact(project_id, id)
  if (!a.data) return a.error ? <li className={styles.meta}>Saved output unavailable.</li> : null
  const href = `${projectHref(project_id)}/materials?artifact=${encodeURIComponent(id)}`
  return <li>{a.data.mime_type.startsWith('image/') ? <img className={styles.thumb} src={artifactContentUrl(project_id, id, 'inline')} alt={a.data.filename} loading="lazy" /> : null}<Link href={href}>{a.data.filename}</Link> <span className={styles.meta}>{a.data.kind} · {a.data.origin}</span></li>
}

function MeasurementDetails({ project_id, file, run_id }: { project_id: string, file: WorkspaceFile, run_id: string }) {
  const results = useRunResults(project_id, run_id)
  const rows = useMeasurements(project_id, run_id, { limit: 10 })
  const media = results.data ? [...results.data.chart_artifact_ids, ...results.data.annotated_media_artifact_ids] : []
  return <div className={styles.contextBox}>
    <div className={styles.actions}><Link href={runHref(project_id, run_id)}>Open run and full results</Link><a href={catalogApi.contentUrl(project_id, file.id)} download={file.name}>Export saved measurements</a></div>
    {results.error && <><ErrorNotice error={results.error} /><button type="button" onClick={() => void results.refetch()}>Retry</button></>}
    {results.data && <p className={styles.meta}>{results.data.measurement_count} saved measurements</p>}
    {media.length > 0 ? <><h3>Saved charts and media</h3><ul className={styles.gallery}>{media.map(id => <GalleryItem key={id} project_id={project_id} id={id} />)}</ul></> : results.data ? <p className={styles.meta}>No saved chart for this run.</p> : null}
    {rows.error ? <ErrorNotice error={rows.error} /> : rows.items.length > 0 && <><h3>Sample of saved measurements</h3><ul className={styles.sample}>{rows.items.slice(0, 10).map(m => <MeasurementRow key={m.id} m={m} />)}</ul></>}
    {results.data?.warnings.length ? <><h3>Warnings</h3><ul>{results.data.warnings.map((w, i) => <li key={`${w.code}-${i}`}>{w.message}</li>)}</ul></> : null}
  </div>
}
