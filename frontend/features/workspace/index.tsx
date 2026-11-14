'use client'

import Link from 'next/link'
import { useState, type KeyboardEvent } from 'react'
import type { Artifact } from '@/contracts/api'
import { useRouter, useSearchParams } from 'next/navigation'
import { artifactContentUrl } from '@/lib/api'
import { useArtifact, useArtifacts, useExperiments } from '@/lib/queries'
import { ErrorNotice, PageMore, artifactHref, projectHref, runHref } from '@/features/execution/feedback'
import { ReportComposer } from '@/features/reports'
import { ArtifactPreview } from './preview'
import styles from '@/features/execution/sol.module.css'

function ArtifactDetails({ project_id, artifact_id }: { project_id: string, artifact_id: string }) {
  const query = useArtifact(project_id, artifact_id), experiments = useExperiments(project_id)
  if (query.error) return <ErrorNotice error={query.error} />
  const artifact = query.data
  if (!artifact) return <p>Loading artifact…</p>
  if (artifact.project_id !== project_id) return <p role="alert">Artifact unavailable in this project.</p>
  const associations = experiments.items.filter(e => e.id === artifact.experiment_id || e.input_artifact_ids.includes(artifact.id))
  return <section><h2>{artifact.filename}</h2><dl className={styles.metadata}><dt>Kind</dt><dd>{artifact.kind}</dd><dt>Type</dt><dd>{artifact.mime_type}</dd><dt>Category</dt><dd>{category(artifact)}</dd><dt>Origin</dt><dd>{artifact.origin}{artifact.origin === 'simulated' ? ' · synthetic experimental data' : ''}</dd><dt>Size</dt><dd>{artifact.size_bytes.toLocaleString()} bytes</dd><dt>Created</dt><dd>{new Date(artifact.created_at).toLocaleString()}</dd><dt>SHA-256</dt><dd><code>{artifact.sha256}</code></dd><dt>Run</dt><dd>{artifact.run_id ? <Link href={runHref(project_id, artifact.run_id)}>Execution and provenance</Link> : 'Not linked to an execution'}</dd></dl><div className={styles.actions}><a href={artifactContentUrl(project_id, artifact.id)} download={artifact.filename}>Download {artifact.filename}</a>{artifact.kind === 'report' && <Link href={`${projectHref(project_id)}/reports/${encodeURIComponent(artifact.id)}`}>Open report</Link>}</div><h3>Experiment associations</h3><ErrorNotice error={experiments.error} />{associations.map(e => <p key={e.id}><Link href={`${projectHref(project_id)}/studio?experiment=${encodeURIComponent(e.id)}`}>{e.title}</Link></p>)}{!associations.length && <p>No association found among loaded experiments.</p>}<PageMore has_more={experiments.has_next_page} loading={experiments.isFetchingNextPage} load={experiments.load_next_page} /><h3>Parent evidence</h3>{artifact.parent_artifact_ids.length ? <ul>{artifact.parent_artifact_ids.map(id => <li key={id}><Link href={artifactHref(project_id, id)}>{id}</Link></li>)}</ul> : <p>No parent artifacts recorded.</p>}<h3>Preview</h3><ArtifactPreview project_id={project_id} artifact={artifact} /></section>
}
const CATEGORIES = ['Original inputs', 'Simulated data', 'Generated outputs', 'Provenance and logs'] as const
// Groups come only from saved artifact metadata; they are not filesystem folders.
function category(a: Artifact): string {
  if (a.kind === 'environment' || a.kind === 'log') return 'Provenance and logs'
  if (a.origin === 'simulated') return 'Simulated data'
  if (a.origin === 'generated' || a.origin === 'derived') return 'Generated outputs'
  return 'Original inputs'
}
const ORIGIN_LABEL: Record<Artifact['origin'], string> = { observed: 'Observed', reference: 'Reference', simulated: 'Simulated (synthetic)', derived: 'Derived', generated: 'Generated' }
function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  const units = ['KiB', 'MiB', 'GiB']; let value = bytes / 1024, i = 0
  while (value >= 1024 && i < units.length - 1) { value /= 1024; i++ }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[i]}`
}
function moveFocus(event: KeyboardEvent<HTMLElement>) {
  const keys = ['ArrowDown', 'ArrowUp', 'Home', 'End']
  // Leave summary (group toggle) keys to the browser so native expand/collapse keeps working.
  if (!keys.includes(event.key) || !(event.target as HTMLElement).closest('button[data-artifact]')) return
  // Only rows in expanded groups are reachable; collapsed rows have no layout boxes.
  const items = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('button[data-artifact]')).filter(b => b.getClientRects().length > 0)
  if (!items.length) return
  const index = items.indexOf(document.activeElement as HTMLButtonElement)
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1 : index < 0 ? 0 : Math.min(items.length - 1, Math.max(0, index + (event.key === 'ArrowDown' ? 1 : -1)))
  event.preventDefault()
  items[next].focus()
}

export function WorkspaceScreen({ project_id }: { project_id: string }) {
  const search = useSearchParams(), router = useRouter()
  const [kind, setKind] = useState(''), [name, setName] = useState(''), [groupBy, setGroupBy] = useState<'category' | 'run'>('category')
  const artifacts = useArtifacts(project_id, { kind: kind || undefined, run_id: search.get('run') ?? undefined, experiment_id: search.get('experiment') ?? undefined })
  const selected = search.get('artifact')
  function select(id: string) {
    const params = new URLSearchParams(search.toString()); params.set('artifact', id); router.replace(`${projectHref(project_id)}/workspace?${params}`, { scroll: false })
    if (window.matchMedia('(max-width: 767px)').matches) requestAnimationFrame(() => document.getElementById('artifact-details')?.scrollIntoView({ block: 'start' }))
  }
  const needle = name.trim().toLowerCase()
  const visible = artifacts.items.filter(a => a.project_id === project_id && (!needle || [a.filename, a.kind, a.mime_type, a.origin].some(v => v.toLowerCase().includes(needle))))
  const groups = new Map<string, Artifact[]>()
  if (groupBy === 'category') CATEGORIES.forEach(c => groups.set(c, []))
  for (const a of visible) {
    const key = groupBy === 'category' ? category(a) : a.run_id ? `Run ${a.run_id}` : 'Uploaded or not linked to a run'
    groups.set(key, [...(groups.get(key) ?? []), a])
  }
  return <main className={styles.screen}><h1>Project Workspace</h1><p>Original inputs, derived evidence, code, charts, and reports saved in this project. Saved files are immutable; groups are based on each file&apos;s recorded origin and run, not on folders.</p><div className={styles.grid}><section aria-label="Artifact explorer">
    <div className={styles.explorerFilters}><label>Artifact kind<select value={kind} onChange={e => setKind(e.target.value)}><option value="">All kinds</option>{['document', 'dataset', 'image', 'video', 'audio', 'code', 'chart', 'report', 'log', 'environment'].map(k => <option key={k}>{k}</option>)}</select></label><label>Search loaded files<input type="search" value={name} placeholder="Name, type, or origin" onChange={e => setName(e.target.value)} /></label><label>Group by<select value={groupBy} onChange={e => setGroupBy(e.target.value as 'category' | 'run')}><option value="category">Origin category</option><option value="run">Run</option></select></label></div>
    <ErrorNotice error={artifacts.error} />{artifacts.isPending && <p role="status">Loading files…</p>}
    {!artifacts.isPending && !artifacts.error && !artifacts.items.length && <p>No saved files match these filters. Upload experimental inputs in Studio.</p>}
    {!!artifacts.items.length && !visible.length && <p role="status">No loaded file matches “{name}”.{artifacts.has_next_page ? ' Load more files to search further.' : ''}</p>}
    {!!visible.length && <div className={styles.explorer} onKeyDown={moveFocus}>{[...groups].filter(([, items]) => items.length).map(([group, items]) => <details key={group} open className={styles.explorerGroup}><summary>{group} <span className={styles.explorerCount}>({items.length})</span></summary><ul className={styles.explorerList} aria-label={group}>{items.map(a => <li key={a.id}><button type="button" data-artifact aria-current={selected === a.id ? 'true' : undefined} className={styles.explorerItem} onClick={() => select(a.id)}><span className={styles.explorerName}>{a.filename}</span><span className={styles.explorerMeta}>{a.kind} · {a.mime_type} · {formatSize(a.size_bytes)} · {ORIGIN_LABEL[a.origin] ?? a.origin}{groupBy === 'category' && a.run_id ? ' · from a run' : ''}</span></button></li>)}</ul></details>)}</div>}
    <PageMore has_more={artifacts.has_next_page} loading={artifacts.isFetchingNextPage} load={artifacts.load_next_page} />
  </section><div id="artifact-details">{selected ? <ArtifactDetails key={selected} project_id={project_id} artifact_id={selected} /> : <section><h2>Inspect your evidence</h2><p>Select a saved file to inspect its preview, origin, parent evidence, and execution history. Use the arrow keys to move through the list.</p></section>}</div></div><ReportComposer project_id={project_id} /></main>
}
