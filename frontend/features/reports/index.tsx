'use client'

import Link from 'next/link'
import { useRef, useState } from 'react'
import type { StartRunVariables } from '@/lib/queries'
import { ApiError, artifactContentUrl, commandKey } from '@/lib/api'
import { terminal, useArtifact, useCapabilities, useExperiments, useProject, useRuns, useSources, useStartRun } from '@/lib/queries'
import { ArtifactPreview } from '@/features/workspace/preview'
import { ErrorNotice, PageMore, artifactHref, runHref } from '@/features/execution/feedback'
import styles from '@/features/execution/sol.module.css'

export function ReportComposer({ project_id }: { project_id: string }) {
  const capabilities = useCapabilities(), project = useProject(project_id)
  const experiments = useExperiments(project_id), sources = useSources(project_id)
  const [experiment, setExperiment] = useState(''), [title, setTitle] = useState(''), [evidence, setEvidence] = useState<string[]>([]), [references, setReferences] = useState<string[]>([])
  const runs = useRuns(project_id, { kind: 'analysis', experiment_id: experiment || undefined })
  const start = useStartRun(), request = useRef<StartRunVariables | null>(null)
  const [accepted, setAccepted] = useState<string | null>(null), [submitted, setSubmitted] = useState(false)
  const locked = start.isPending || submitted
  const eligible = runs.items.filter(r => r.input.kind === 'analysis' && r.input.experiment_id === experiment && terminal(r))
  async function submit() {
    setSubmitted(true)
    request.current ??= { project_id, body: { kind: 'report', experiment_id: experiment, evidence_run_ids: evidence, source_ids: references, title: title.trim(), format: 'markdown' }, command: { idempotency_key: commandKey() } }
    try { const response = await start.mutateAsync(request.current); setAccepted(response.data.id) } catch { /* Explicit retry uses the exact same request. */ }
  }
  function toggle(items: string[], id: string) { return items.includes(id) ? items.filter(v => v !== id) : [...items, id] }
  if (!capabilities.data?.features.markdown_reports) return <section><h2>Scientific reports</h2><p>Markdown report generation is unavailable on this backend.</p></section>
  if (accepted) return <section><h2>Report generation accepted</h2><p>The report is not complete yet. <Link href={runHref(project_id, accepted)}>Follow the report run</Link>.</p><button onClick={() => { request.current = null; setSubmitted(false); setAccepted(null); start.reset(); setEvidence([]); setTitle('') }}>Compose another report</button></section>
  const rejected = start.error instanceof ApiError && [400, 403, 404, 412, 413, 415, 422, 428].includes(start.error.status)
  return <section>
    <h2>Generate a scientific report</h2>
    <p>Select saved analysis evidence. A successful report does not imply the experiment succeeded.</p>
    {project.data?.status === 'archived' && <p className={styles.notice}>Restore the project before generating new reports.</p>}
    <ErrorNotice error={experiments.error ?? sources.error ?? runs.error ?? start.error} />
    <form onSubmit={e => { e.preventDefault(); void submit() }}>
      <label>Experiment<select required disabled={locked} value={experiment} onChange={e => { setExperiment(e.target.value); setEvidence([]) }}>
        <option value="">Choose an experiment</option>
        {experiments.items.map(e => <option value={e.id} key={e.id}>{e.title}</option>)}
      </select></label>
      <PageMore has_more={experiments.has_next_page} loading={experiments.isFetchingNextPage} load={experiments.load_next_page} />
      <label>Report title<input required value={title} disabled={locked} onChange={e => setTitle(e.target.value)} /></label>
      <fieldset disabled={locked || !experiment}>
        <legend>Analysis evidence</legend>
        {eligible.map(r => <label key={r.id}><input type="checkbox" checked={evidence.includes(r.id)} onChange={() => setEvidence(toggle(evidence, r.id))} />{r.id} · {r.status}{r.status !== 'succeeded' ? ' · partial evidence, limitations must be reported' : ''}</label>)}
        {!eligible.length && <p>No eligible terminal analysis runs among the loaded records.</p>}
        <PageMore has_more={runs.has_next_page} loading={runs.isFetchingNextPage} load={runs.load_next_page} />
      </fieldset>
      <fieldset disabled={locked}>
        <legend>Saved literature sources</legend>
        {sources.items.map(s => <label key={s.id}><input type="checkbox" checked={references.includes(s.id)} onChange={() => setReferences(toggle(references, s.id))} />{s.title} · {s.retrieval_status.replaceAll('_', ' ')}</label>)}
        <PageMore has_more={sources.has_next_page} loading={sources.isFetchingNextPage} load={sources.load_next_page} />
      </fieldset>
      <button disabled={start.isPending || project.data?.status !== 'active' || !experiment || !title.trim() || !evidence.length || rejected}>{start.isPending ? 'Submitting report run…' : start.error ? 'Retry the same report submission' : 'Generate Markdown report'}</button>
    </form>
    {start.error && <p>The original request is retained. <Link href={runHref(project_id, '').replace(/\/$/, '')}>Check run history</Link> before starting another report.</p>}
    {rejected && <button onClick={() => { request.current = null; setSubmitted(false); start.reset() }}>Edit the rejected request</button>}
  </section>
}
export function ReportScreen({ project_id, artifact_id }: { project_id: string, artifact_id: string }) {
  const query = useArtifact(project_id, artifact_id)
  if (query.error) return <main className={styles.screen}><h1>Report unavailable</h1><ErrorNotice error={query.error} /></main>
  const artifact = query.data
  if (!artifact) return <main className={styles.screen} aria-busy="true">Loading saved report…</main>
  if (artifact.project_id !== project_id || artifact.kind !== 'report' || !['text/markdown', 'text/plain'].includes(artifact.mime_type.split(';')[0])) return <main className={styles.screen}><h1>Report unavailable</h1><p>This artifact is not a supported Markdown report in this project.</p></main>
  return <main className={styles.screen}><h1>{artifact.filename}</h1><p>Saved {new Date(artifact.created_at).toLocaleString()}. Conclusions and experiment status are described in the recorded evidence.</p><div className={styles.actions}><a href={artifactContentUrl(project_id, artifact_id)}>Download Markdown</a><Link href={artifactHref(project_id, artifact_id)}>Inspect report provenance and parent evidence</Link>{artifact.run_id && <Link href={runHref(project_id, artifact.run_id)}>Report generation run</Link>}</div><ArtifactPreview project_id={project_id} artifact={artifact} /></main>
}
