'use client'
/* eslint-disable @next/next/no-img-element -- Artifact previews require session cookies that the image optimizer cannot forward. */

import Link from 'next/link'
import { ReportCard } from '@/features/reports/ReportCard'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { Artifact, Claim, Measurement, Source } from '@/contracts/api'
import type { WorkspaceFile } from '@/contracts/catalog'
import { api, artifactContentUrl, readText } from '@/lib/api'
import { catalogApi } from '@/lib/catalog'
import { keys, useArtifact, useExperiment, useMeasurements, useRun, useRunResults } from '@/lib/queries'
import { projectHref, runHref } from '@/features/execution/feedback'
import styles from './materials.module.css'

export type MaterialCardProps = {
  project_id: string, file: WorkspaceFile, onInspect?: (id: string) => void,
  /** Optional: marks the card whose inspector is open. */
  selected?: boolean,
}

const date = (value: string | null | undefined) => value ? new Date(value).toLocaleDateString() : null
const bytes = (n: number) => n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KiB` : `${(n / 1048576).toFixed(1)} MiB`
const RETRIEVAL: Record<Source['retrieval_status'], string> = { metadata_only: 'Metadata only', abstract_retrieved: 'Abstract retrieved', full_text_retrieved: 'Full text retrieved', failed: 'Retrieval failed' }
const ORIGIN_LABEL: Record<string, string> = { artifact: 'Artifact', source: 'Source', claim: 'Finding', experiment: 'Experiment plan', run: 'Run', run_measurements: 'Measurement set' }

/** Type label from authoritative fields only (file kind, origin, artifact kind). Tags never change type. */
export function materialTypeLabel(file: WorkspaceFile) {
  if (file.file_kind === 'note') return 'Organizational note'
  if (file.origin?.type === 'artifact') return file.artifact_kind ? `${file.artifact_kind[0].toUpperCase()}${file.artifact_kind.slice(1)}` : 'Artifact'
  return file.origin ? ORIGIN_LABEL[file.origin.type] ?? 'Material' : 'Material'
}

/** Becomes true once the element is near the viewport; card hydration and previews wait for it. */
function useVisible() {
  const ref = useRef<HTMLElement | null>(null)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el || visible) return
    if (typeof IntersectionObserver === 'undefined') { const t = setTimeout(() => setVisible(true), 0); return () => clearTimeout(t) }
    const observer = new IntersectionObserver(entries => { if (entries.some(e => e.isIntersecting)) { setVisible(true); observer.disconnect() } }, { rootMargin: '200px' })
    observer.observe(el)
    return () => observer.disconnect()
  }, [visible])
  return { ref, visible }
}

function plainText(markdown: string) {
  return markdown.replace(/```[\s\S]*?```/g, ' ').replace(/!\[[^\]]*\]\([^)]*\)/g, ' ').replace(/\[([^\]]*)\]\([^)]*\)/g, '$1').replace(/[#>*_`~|]/g, '').replace(/\s+/g, ' ').trim()
}

function Failed({ error, retry }: { error: unknown, retry: () => unknown }) {
  return <p className={styles.cardError} role="status">Details could not load{error instanceof Error ? `: ${error.message}` : '.'} <button type="button" onClick={() => void retry()}>Retry</button></p>
}
const Loading = () => <p className={styles.cardSkeleton} aria-busy="true">Loading details…</p>

/**
 * Type-aware catalog card shared by Materials views and the Research desk. The title inspects the material
 * (when `onInspect` is supplied); workflow links are separate siblings. Hydration loads only when visible.
 */
export function MaterialCard({ project_id, file, onInspect, selected }: MaterialCardProps) {
  const { ref, visible } = useVisible()
  const origin = file.origin
  if (origin?.type === 'artifact' && file.artifact_kind === 'report') return <section ref={ref} data-file-id={file.id}>
    {visible ? <ReportCard project_id={project_id} artifact_id={origin.id} onInspect={onInspect ? () => onInspect(file.id) : undefined} /> : <Loading />}
  </section>
  let body: ReactNode
  if (file.file_kind === 'note') body = <NoteBody project_id={project_id} file={file} visible={visible} />
  else if (origin?.type === 'source') body = <SourceBody project_id={project_id} id={origin.id} visible={visible} />
  else if (origin?.type === 'claim') body = <ClaimBody project_id={project_id} id={origin.id} visible={visible} />
  else if (origin?.type === 'experiment') body = <ExperimentBody project_id={project_id} id={origin.id} visible={visible} />
  else if (origin?.type === 'run_measurements') body = <MeasurementBody project_id={project_id} run_id={origin.id} visible={visible} />
  else if (origin?.type === 'run') body = <RunBody project_id={project_id} id={origin.id} visible={visible} />
  else if (origin?.type === 'artifact') body = <ArtifactBody project_id={project_id} file={file} id={origin.id} visible={visible} />
  else body = <p className={styles.meta}>Open the inspector for this material&apos;s saved details.</p>
  return <article ref={ref}className={styles.card} data-file-id={file.id} aria-current={selected ? 'true' : undefined}>
    <div className={styles.cardBadges}><span className={styles.badge}>{materialTypeLabel(file)}</span>{file.scientific_origin && <span className={styles.badge}>{file.scientific_origin}</span>}{file.status === 'trashed' && <span className={styles.badge}>In trash</span>}</div>
    <h3 className={styles.cardTitle}>{onInspect ? <button type="button" className={styles.titleButton} onClick={() => onInspect(file.id)}>{file.name}</button> : file.name}</h3>
    {body}
    {file.tags.length > 0 && <div className={styles.tags}>{file.tags.map(t => <span className={styles.tag} key={t.slug}>{t.slug}</span>)}</div>}
  </article>
}

function NoteBody({ project_id, file, visible }: { project_id: string, file: WorkspaceFile, visible: boolean }) {
  const content = useQuery({ queryKey: ['project', project_id, 'catalog-content', file.id, file.content_revision, file.content_sha256, 'preview'], enabled: visible, queryFn: ({ signal }) => readText(catalogApi.contentUrl(project_id, file.id), signal), retry: false })
  return <>
    {!visible || content.isPending ? <Loading /> : content.error ? <Failed error={content.error} retry={content.refetch} /> : <p className={styles.clamp3}>{plainText(content.data.text) || <span className={styles.muted}>This note has no content.</span>}</p>}
    <p className={styles.meta}>{file.mime_type === 'text/markdown' ? 'Markdown' : 'Plain text'} · edited {date(file.updated_at)}</p>
  </>
}

function SourceBody({ project_id, id, visible }: { project_id: string, id: string, visible: boolean }) {
  const q = useQuery({ queryKey: keys.detail(project_id, 'sources', id), queryFn: ({ signal }) => api.sources.get(project_id, id, signal), enabled: visible, retry: false })
  if (!visible || q.isPending) return <Loading />
  if (q.error) return <Failed error={q.error} retry={q.refetch} />
  const s = q.data.data as Source & { full_text?: { truncated?: boolean } | null }
  const authors = s.authors.length > 2 ? `${s.authors.slice(0, 2).join(', ')} et al.` : s.authors.join(', ')
  const year = s.published_at ? s.published_at.slice(0, 4) : null
  return <>
    {(authors || year) && <p className={styles.meta}>{[authors, year].filter(Boolean).join(' · ')}</p>}
    <p className={styles.clamp3}>{s.abstract || <span className={styles.muted}>No abstract saved.</span>}</p>
    <p className={styles.cardBadges}><span className={styles.badge}>{RETRIEVAL[s.retrieval_status] ?? s.retrieval_status}</span>{s.full_text?.truncated && <span className={styles.badge}>Partial extraction</span>}</p>
    <p className={styles.meta}>Added {date(s.created_at)} · {s.provider}</p>
  </>
}

function ClaimBody({ project_id, id, visible }: { project_id: string, id: string, visible: boolean }) {
  const q = useQuery({ queryKey: keys.detail(project_id, 'claims', id), queryFn: ({ signal }) => api.claims.get(project_id, id, signal), enabled: visible, retry: false })
  if (!visible || q.isPending) return <Loading />
  if (q.error) return <Failed error={q.error} retry={q.refetch} />
  const c: Claim = q.data.data
  const base = projectHref(project_id)
  return <>
    <p className={styles.cardBadges}><span className={styles.badge}>{c.kind === 'hypothesis' ? 'Hypothesis · proposed' : c.kind === 'observation' ? 'Observation' : 'Inference'}</span></p>
    <p className={styles.clamp3}>{c.text}</p>
    {c.limitations[0] && <p className={`${styles.clamp2} ${styles.meta}`}>Limitation: {c.limitations[0]}</p>}
    <p className={styles.meta}>{c.citations.length} citation{c.citations.length === 1 ? '' : 's'} · {c.measurement_ids.length} measurement reference{c.measurement_ids.length === 1 ? '' : 's'} · saved {date(c.created_at)}</p>
    <details className={styles.evidence}><summary>Evidence and qualifications</summary>
      {c.citations.length > 0 && <ul>{c.citations.map((ct, i) => <li key={`${ct.source_id}-${i}`}><Link href={`${base}/materials?source=${encodeURIComponent(ct.source_id)}`}>Cited source {i + 1}</Link>{ct.locator ? ` · ${ct.locator}` : ''}{ct.excerpt ? ` — ${ct.excerpt}` : ''}</li>)}</ul>}
      {c.measurement_ids.length > 0 && <p><Link href={runHref(project_id, c.run_id)}>Inspect referenced measurements in the run</Link></p>}
      {c.evidence.length > 0 && <ul>{c.evidence.map((e, i) => <li key={`${e.artifact_id}-${i}`}><Link href={`${base}/materials?artifact=${encodeURIComponent(e.artifact_id)}`}>Evidence {i + 1}</Link>{e.frame_index !== null ? ` · frame ${e.frame_index}` : ''}{e.time_s !== null ? ` · ${e.time_s} s` : ''}{e.row_index !== null ? ` · row ${e.row_index}` : ''}</li>)}</ul>}
      {c.assumptions.length > 0 && <><p className={styles.meta}>Assumptions</p><ul>{c.assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul></>}
      {c.limitations.length > 0 && <><p className={styles.meta}>Limitations</p><ul>{c.limitations.map((a, i) => <li key={i}>{a}</li>)}</ul></>}
      {!c.citations.length && !c.evidence.length && !c.measurement_ids.length && <p className={styles.muted}>No citations or evidence references were recorded.</p>}
    </details>
  </>
}

function ExperimentBody({ project_id, id, visible }: { project_id: string, id: string, visible: boolean }) {
  const q = useExperiment(project_id, visible ? id : null)
  if (!visible || q.isPending) return <Loading />
  if (q.error || !q.data) return <Failed error={q.error} retry={q.refetch} />
  const e = q.data
  return <>
    <p className={styles.meta}>{e.method} · revision {e.revision} · {e.input_artifact_ids.length} input{e.input_artifact_ids.length === 1 ? '' : 's'} · saved {date(e.updated_at)}</p>
    <p className={styles.clamp2}>{e.hypothesis || <span className={styles.muted}>Hypothesis not recorded</span>}</p>
    <p><Link href={`${projectHref(project_id)}/studio?experiment=${encodeURIComponent(e.id)}`}>Open in Studio</Link></p>
  </>
}

function RunBody({ project_id, id, visible }: { project_id: string, id: string, visible: boolean }) {
  const q = useRun(project_id, visible ? id : null)
  if (!visible || q.isPending) return <Loading />
  if (q.error || !q.data) return <Failed error={q.error} retry={q.refetch} />
  const r = q.data
  const kind = (r.input as { kind: string }).kind
  return <>
    <p className={styles.meta}>{kind === 'agent' ? 'Research' : kind === 'analysis' ? 'Analysis' : kind === 'report' ? 'Report generation' : kind === 'paper_ingest' ? 'Paper ingestion' : kind} · {r.status}{r.finished_at ? ` · finished ${date(r.finished_at)}` : ''}</p>
    {r.result_summary && <p className={styles.clamp3}>{r.result_summary}</p>}
    {r.error && <p className={styles.meta}>Error: {r.error.message}</p>}
    <p><Link href={runHref(project_id, r.id)}>Open run</Link></p>
  </>
}

export function MeasurementRow({ m }: { m: Measurement }) {
  return <li>{m.quantity}: {m.status === 'valid' && m.value !== null ? m.value : m.status === 'rejected' ? 'Rejected' : 'Missing'} {m.unit}{m.uncertainty.absolute !== null ? ` ± ${m.uncertainty.absolute}` : ' · Uncertainty not recorded'} · {m.data_origin} · calibration {m.calibration_mode === 'none' ? 'none' : 'reference length'}{m.time_s !== null ? ` · t=${m.time_s} s` : ''}</li>
}

function ChartThumb({ project_id, id }: { project_id: string, id: string }) {
  const a = useArtifact(project_id, id)
  const [failed, setFailed] = useState(false)
  if (!a.data || failed || !a.data.mime_type.startsWith('image/')) return a.error || failed ? <p className={styles.meta}>Chart preview unavailable.</p> : null
  return <img className={styles.thumb} src={artifactContentUrl(project_id, id, 'inline')} alt={a.data.filename} loading="lazy" onError={() => setFailed(true)} />
}

function MeasurementBody({ project_id, run_id, visible }: { project_id: string, run_id: string, visible: boolean }) {
  const run = useRun(project_id, visible ? run_id : null)
  const results = useRunResults(project_id, visible ? run_id : null)
  const rows = useMeasurements(project_id, visible ? run_id : '', { limit: 3 })
  const input = run.data?.input
  const experimentId = input?.kind === 'analysis' ? input.experiment_id : null
  const experiment = useExperiment(project_id, experimentId)
  if (!visible || run.isPending) return <Loading />
  if (run.error || !run.data) return <Failed error={run.error} retry={run.refetch} />
  const chart = results.data?.chart_artifact_ids[0]
  return <>
    <p className={styles.meta}>{experiment.data?.title ?? (experimentId ? 'Experiment' : 'No experiment recorded')} · {run.data.status}{run.data.started_at ? ` · executed ${date(run.data.started_at)}` : ''}{results.data ? ` · ${results.data.measurement_count} saved measurements` : ''}</p>
    {results.error ? <Failed error={results.error} retry={results.refetch} /> : chart ? <ChartThumb project_id={project_id} id={chart} /> : results.data ? <p className={styles.meta}>No saved chart for this run.</p> : null}
    {rows.error ? <Failed error={rows.error} retry={rows.refetch} /> : rows.items.length > 0 && <><p className={styles.meta}>Sample of saved measurements</p><ul className={styles.sample}>{rows.items.slice(0, 3).map(m => <MeasurementRow key={m.id} m={m} />)}</ul></>}
    <p><Link href={runHref(project_id, run_id)}>Inspect this run&apos;s results</Link></p>
  </>
}

function ArtifactBody({ project_id, file, id, visible }: { project_id: string, file: WorkspaceFile, id: string, visible: boolean }) {
  const q = useArtifact(project_id, visible ? id : null)
  const [imageFailed, setImageFailed] = useState(false)
  const [videoFailed, setVideoFailed] = useState(false)
  if (!visible || q.isPending) return <Loading />
  if (q.error || !q.data) return <Failed error={q.error} retry={q.refetch} />
  const a: Artifact = q.data
  const base = projectHref(project_id)
  const added = `added ${date(a.created_at)}`
  if (a.kind === 'image' || a.kind === 'chart') return <>
    {!imageFailed && a.mime_type.startsWith('image/') ? <img className={styles.thumb} src={artifactContentUrl(project_id, a.id, 'inline')} alt={a.filename} loading="lazy" onError={() => setImageFailed(true)} /> : <p className={styles.placeholder}>Image preview unavailable</p>}
    <p className={styles.meta}>{a.metadata.width_px && a.metadata.height_px ? `${a.metadata.width_px}×${a.metadata.height_px} px · ` : ''}{a.origin} · {added}</p>
  </>
  if (a.kind === 'video') return <>
    {a.mime_type.startsWith('video/') && !videoFailed ? <video className={styles.thumb} src={artifactContentUrl(project_id, a.id, 'inline')} controls preload="none" aria-label={`Preview ${a.filename}`} onError={() => setVideoFailed(true)} /> : <p className={styles.placeholder} aria-label="Video">Video preview unavailable</p>}
    {a.metadata.duration_ms != null && <p className={styles.meta}>{(a.metadata.duration_ms / 1000).toFixed(1)} s</p>}
    <p className={styles.meta}>{a.origin} · {added}</p>
  </>
  if (a.kind === 'report') return <>
    <p className={styles.meta}>{a.origin} · {added}</p>
    <p><Link href={`${base}/reports/${encodeURIComponent(a.id)}`}>Open report</Link></p>
  </>
  return <>
    <p className={styles.meta}>{a.mime_type} · {bytes(a.size_bytes || file.size_bytes)} · {a.origin} · {added}</p>
    {(a.experiment_id || a.run_id) && <p className={styles.actions}>{a.experiment_id && <Link href={`${base}/studio?experiment=${encodeURIComponent(a.experiment_id)}`}>Associated experiment</Link>}{a.run_id && <Link href={runHref(project_id, a.run_id)}>Producing run</Link>}</p>}
  </>
}
