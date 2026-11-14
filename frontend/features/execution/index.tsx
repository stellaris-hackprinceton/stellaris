'use client'

import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import type { Run } from '@/contracts/api'
import type { StartRunVariables } from '@/lib/queries'
import { ApiError, commandKey } from '@/lib/api'
import { terminal, useCancelRun, useExperiment, useProject, useRun, useRunLogs, useRunResults, useStartRun } from '@/lib/queries'
import { TrackerScreen } from './TrackerScreen'
import { ResultsSlot } from '@/providers/feature-bridge'
import { ErrorNotice, PageMore, artifactHref, projectHref, runHref } from './feedback'
import styles from './sol.module.css'

function activityKind(kind: Run['input']['kind']) {
  return kind === 'agent' ? 'Research' : kind === 'analysis' ? 'Analysis' : 'Report'
}
function activityState(status: Run['status']) {
  const labels: Record<Run['status'], string> = { queued: 'Queued', running: 'In progress', awaiting_approval: 'Needs approval', cancelling: 'Cancellation requested', succeeded: 'Completed', failed: 'Failed', cancelled: 'Cancelled' }
  return labels[status]
}

function RunActions({ run, project_id }: { run: Run, project_id: string }) {
  const project = useProject(project_id), cancel = useCancelRun(), start = useStartRun()
  const experiment = useExperiment(project_id, 'experiment_id' in run.input ? run.input.experiment_id : undefined)
  const cancelKey = useRef<string | null>(null), rerunRequest = useRef<StartRunVariables | null>(null)
  const [review, setReview] = useState(false)
  const [accepted, setAccepted] = useState<string | null>(null)
  async function cancelRun() { cancelKey.current ??= commandKey(); try { await cancel.mutateAsync({ project_id, run_id: run.id, command: { idempotency_key: cancelKey.current } }) } catch { /* Display mutation error without altering server state. */ } }
  async function rerun() {
    if (run.input.kind === 'agent') return
    if (!rerunRequest.current) {
      const input = run.input.kind === 'analysis' && experiment.data ? { ...run.input, experiment_revision: experiment.data.revision } : run.input
      rerunRequest.current = { project_id, body: input, command: { idempotency_key: commandKey() } }
    }
    try { const result = await start.mutateAsync(rerunRequest.current); setAccepted(result.data.id) } catch { /* Reuse the accepted-or-unresolved command on retry. */ }
  }
  const stalePlan = start.error instanceof ApiError && start.error.error.code === 'EXPERIMENT_REVISION_CONFLICT'
  return <><ErrorNotice error={cancel.error ?? start.error} /><div className={styles.actions}>{!terminal(run) && <button disabled={cancel.isPending || run.status === 'cancelling'} onClick={() => void cancelRun()}>{cancel.isPending ? 'Requesting cancellation…' : run.status === 'cancelling' ? 'Cancellation pending' : 'Cancel run'}</button>}{terminal(run) && run.input.kind !== 'agent' && <button disabled={project.data?.status === 'archived' || !!accepted} onClick={() => setReview(true)}>Review a new run</button>}</div>{review && !accepted && <section><h2>Review before rerunning</h2><p>This submits a new run. The earlier evidence remains unchanged.</p><pre>{JSON.stringify(run.input, null, 2)}</pre>{run.input.kind === 'analysis' && experiment.data && experiment.data.revision !== run.input.experiment_revision && <p className={styles.notice}>The plan changed from revision {run.input.experiment_revision} to {experiment.data.revision}. New analysis uses that latest saved plan. Review it in Experiments before proceeding.</p>}<ErrorNotice error={experiment.error} /><Link href={`${projectHref(project_id)}/studio?experiment=${'experiment_id' in run.input ? encodeURIComponent(run.input.experiment_id) : ''}`}>Review saved experiment</Link><div className={styles.actions}><button disabled={start.isPending || stalePlan || project.data?.status === 'archived' || !experiment.data} onClick={() => void rerun()}>{start.isPending ? 'Submitting…' : start.error ? 'Retry the same submission' : 'Start a new run with these inputs'}</button>{stalePlan && <button onClick={() => { void experiment.refetch().then(() => { rerunRequest.current = null; start.reset() }) }}>Reload plan for a new review</button>}{!start.error && <button onClick={() => setReview(false)}>Keep existing run</button>}</div></section>}{accepted && <p>New run accepted: <Link href={runHref(project_id, accepted)}>Open run details</Link></p>}</>
}
function Logs({ project_id, run_id }: { project_id: string, run_id: string }) {
  const logs = useRunLogs(project_id, run_id), viewport = useRef<HTMLPreElement>(null), nearEnd = useRef(true)
  useEffect(() => { if (nearEnd.current && viewport.current) viewport.current.scrollTop = viewport.current.scrollHeight }, [logs.items.length])
  return <section><h2>Activity logs</h2><ErrorNotice error={logs.error} />{logs.isPending ? <p>Loading logs…</p> : <pre ref={viewport} tabIndex={0} aria-label="Retained activity logs" onScroll={e => { const element = e.currentTarget; nearEnd.current = element.scrollHeight - element.scrollTop - element.clientHeight < 64 }}>{logs.items.slice(-1000).map(row => `${row.sequence} [${row.stream}] ${row.text.replace(/[\u001b\u0000-\u0008\u000b-\u001f\u007f]/g, '')}`).join('\n') || 'No retained logs yet.'}</pre>}<p>At most 1,000 loaded entries are displayed. Complete retained logs may also be available as a saved output file.</p><PageMore has_more={logs.has_next_page} loading={logs.isFetchingNextPage} load={logs.load_next_page} /></section>
}
function RunDetail({ project_id, run_id }: { project_id: string, run_id: string }) {
  const query = useRun(project_id, run_id), results = useRunResults(project_id, run_id)
  if (query.error) return <ErrorNotice error={query.error} />
  if (!query.data) return <p aria-busy="true">Loading run…</p>
  const run = query.data
  if (run.project_id !== project_id) return <p role="alert">This run is unavailable in this project.</p>
  return <><h1>{activityKind(run.input.kind)} activity</h1><p><code>{run.id}</code><span className={styles.badge}>{activityState(run.status)}</span></p><p>{run.phase ?? 'Waiting for activity details'}</p><progress aria-label="Activity progress" max={1} value={run.progress.fraction ?? undefined} /><p>{run.progress.message}</p><dl className={styles.metadata}><dt>Created</dt><dd>{new Date(run.created_at).toLocaleString()}</dd><dt>Started</dt><dd>{run.started_at ? new Date(run.started_at).toLocaleString() : 'Not started'}</dd><dt>Finished</dt><dd>{run.finished_at ? new Date(run.finished_at).toLocaleString() : 'Not finished'}</dd></dl>{run.result_summary && <p>{run.result_summary}</p>}{run.error && <div className={styles.error} role="alert"><strong>{run.error.code}</strong><p>{run.error.message}</p></div>}<RunActions key={run.id} run={run} project_id={project_id} /><Logs project_id={project_id} run_id={run_id} /><h2>Saved outputs</h2><ErrorNotice error={results.error} />{results.data?.warnings.map((w, i) => <p className={styles.notice} key={`${w.code}:${i}`}>{w.message}</p>)}{run.provenance_artifact_id && <Link href={artifactHref(project_id, run.provenance_artifact_id)}>Inspect provenance</Link>}<ul className={styles.rows}>{run.output_artifact_ids.map((id, index) => <li key={id}><Link href={artifactHref(project_id, id)}>Open saved output {index + 1}</Link></li>)}</ul>{results.data?.report_artifact_id && <p><Link href={`${projectHref(project_id)}/reports/${encodeURIComponent(results.data.report_artifact_id)}`}>Open saved report</Link></p>}{run.input.kind === 'analysis' && <ResultsSlot project_id={project_id} run_id={run_id} />}</>
}
export function ExecutionScreen({ project_id, run_id }: { project_id: string, run_id?: string }) {
  return run_id ? <div className={styles.screen}><Link href={`${projectHref(project_id)}/runs`}>Back to Tracker</Link><RunDetail project_id={project_id} run_id={run_id} /></div> : <RunHistory project_id={project_id} />
}
export function RunHistory({ project_id }: { project_id: string }) {
  return <TrackerScreen project_id={project_id} />
}

