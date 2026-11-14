'use client'

import Link from 'next/link'
import { useState } from 'react'
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
  return <section><h2>{artifact.filename}</h2><dl className={styles.metadata}><dt>Kind</dt><dd>{artifact.kind}</dd><dt>Origin</dt><dd>{artifact.origin}{artifact.origin === 'simulated' ? ' · synthetic experimental data' : ''}</dd><dt>Size</dt><dd>{artifact.size_bytes.toLocaleString()} bytes</dd><dt>Created</dt><dd>{new Date(artifact.created_at).toLocaleString()}</dd><dt>SHA-256</dt><dd><code>{artifact.sha256}</code></dd><dt>Run</dt><dd>{artifact.run_id ? <Link href={runHref(project_id, artifact.run_id)}>Execution and provenance</Link> : 'Not linked to an execution'}</dd></dl><div className={styles.actions}><a href={artifactContentUrl(project_id, artifact.id)}>Download {artifact.filename}</a>{artifact.kind === 'report' && <Link href={`${projectHref(project_id)}/reports/${encodeURIComponent(artifact.id)}`}>Open report</Link>}</div><h3>Experiment associations</h3><ErrorNotice error={experiments.error} />{associations.map(e => <p key={e.id}><Link href={`${projectHref(project_id)}/studio?experiment=${encodeURIComponent(e.id)}`}>{e.title}</Link></p>)}{!associations.length && <p>No association found among loaded experiments.</p>}<PageMore has_more={experiments.has_next_page} loading={experiments.isFetchingNextPage} load={experiments.load_next_page} /><h3>Parent evidence</h3>{artifact.parent_artifact_ids.length ? <ul>{artifact.parent_artifact_ids.map(id => <li key={id}><Link href={artifactHref(project_id, id)}>{id}</Link></li>)}</ul> : <p>No parent artifacts recorded.</p>}<h3>Preview</h3><ArtifactPreview project_id={project_id} artifact={artifact} /></section>
}
export function WorkspaceScreen({ project_id }: { project_id: string }) {
  const search = useSearchParams(), router = useRouter()
  const [kind, setKind] = useState(''), [name, setName] = useState('')
  const artifacts = useArtifacts(project_id, { kind: kind || undefined, run_id: search.get('run') ?? undefined, experiment_id: search.get('experiment') ?? undefined })
  const selected = search.get('artifact')
  function select(id: string) { const params = new URLSearchParams(search.toString()); params.set('artifact', id); router.replace(`${projectHref(project_id)}/workspace?${params}`, { scroll: false }) }
  return <main className={styles.screen}><h1>Project Workspace</h1><p>Original inputs, derived evidence, code, charts, and reports saved in this project.</p><div className={styles.grid}><section aria-label="Artifact browser"><label>Artifact kind<select value={kind} onChange={e => setKind(e.target.value)}><option value="">All kinds</option>{['document', 'dataset', 'image', 'video', 'audio', 'code', 'chart', 'report', 'log', 'environment'].map(k => <option key={k}>{k}</option>)}</select></label><label>Filter loaded files<input type="search" value={name} onChange={e => setName(e.target.value)} /></label><ErrorNotice error={artifacts.error} />{artifacts.isPending && <p>Loading files…</p>}{!artifacts.isPending && !artifacts.error && !artifacts.items.length && <p>No saved files match these filters. Upload experimental inputs in Studio.</p>}<ul className={styles.rows}>{artifacts.items.filter(a => a.filename.toLowerCase().includes(name.toLowerCase())).map(a => <li key={a.id}><button aria-pressed={selected === a.id} onClick={() => select(a.id)}>{a.filename}</button><p>{a.kind} · {a.origin} · {a.size_bytes.toLocaleString()} bytes</p></li>)}</ul><PageMore has_more={artifacts.has_next_page} loading={artifacts.isFetchingNextPage} load={artifacts.load_next_page} /></section>{selected ? <ArtifactDetails key={selected} project_id={project_id} artifact_id={selected} /> : <section><h2>Inspect your evidence</h2><p>Select a saved file to inspect its preview, origin, parent evidence, and execution history.</p></section>}</div><ReportComposer project_id={project_id} /></main>
}
