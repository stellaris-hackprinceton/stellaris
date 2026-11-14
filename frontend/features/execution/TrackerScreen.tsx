'use client'

import Link from 'next/link'
import { useState } from 'react'
import type { Run, RunStatus } from '@/contracts/api'
import { terminal, useExperiment, useRun, useRuns, useWorkspace } from '@/lib/queries'
import { ErrorNotice, PageMore, projectHref, runHref } from './feedback'
import styles from './tracker.module.css'

const LABELS: Record<RunStatus, string> = {
  queued: 'Queued', running: 'In progress', awaiting_approval: 'Needs approval',
  cancelling: 'Cancellation requested', succeeded: 'Execution completed', failed: 'Failed', cancelled: 'Cancelled',
}
const KINDS = { agent: 'Research', analysis: 'Analysis', report: 'Report' } as const

function RunRow({ project_id, run }: { project_id: string; run: Run }) {
  const fraction = run.progress.fraction
  return <li className={styles.run} data-status={run.status}>
    <span className={styles.marker} aria-hidden="true" />
    <div className={styles.runBody}>
      <div className={styles.runHeading}>
        <Link href={runHref(project_id, run.id)}>{KINDS[run.input.kind]} run <span className={styles.identifier}>{run.id.slice(-8)}</span></Link>
        <span className={styles.status} data-status={run.status}>{LABELS[run.status]}</span>
      </div>
      <p className={styles.phase}>{run.progress.message || run.phase || (run.status === 'queued' ? 'Waiting to start' : 'No phase recorded')}</p>
      {(!terminal(run) || fraction !== null) && <div className={styles.progressRow}>
        <progress aria-label={`${KINDS[run.input.kind]} run ${run.id.slice(-8)} progress`} max={1} value={fraction ?? undefined} />
        <span>{fraction === null ? 'Progress not quantified' : `${Math.round(fraction * 100)}%`}</span>
      </div>}
      {run.error && <p className={styles.failure}>{run.error.message} <Link href={runHref(project_id, run.id)}>Inspect failure</Link></p>}
      {run.status === 'awaiting_approval' && <p className={styles.failure}>Waiting for your decision. <Link href={runHref(project_id, run.id)}>Review run</Link></p>}
      {run.result_summary && <p>{run.result_summary}</p>}
      <div className={styles.runMeta}>
        <time dateTime={run.created_at}>Created {new Date(run.created_at).toLocaleString()}</time>
        {run.finished_at && <time dateTime={run.finished_at}>Finished {new Date(run.finished_at).toLocaleString()}</time>}
        {run.output_artifact_ids.length > 0 && <Link href={`${projectHref(project_id)}/materials?artifact=${encodeURIComponent(run.output_artifact_ids[0])}`}>{run.output_artifact_ids.length} saved {run.output_artifact_ids.length === 1 ? 'output' : 'outputs'}</Link>}
      </div>
    </div>
  </li>
}

function ActiveRun({ project_id, id }: { project_id: string; id: string }) {
  const query = useRun(project_id, id)
  if (query.error) return <li><ErrorNotice error={query.error} /><button onClick={() => void query.refetch()}>Reload run</button></li>
  if (!query.data) return <li className={styles.loading} aria-busy="true">Loading active run…</li>
  if (query.data.project_id !== project_id || terminal(query.data)) return null
  return <RunRow project_id={project_id} run={query.data} />
}

function HistoryGroup({ project_id, experiment_id, runs }: { project_id: string; experiment_id?: string; runs: Run[] }) {
  const experiment = useExperiment(project_id, experiment_id)
  return <section className={styles.group}>
    <h3>{experiment_id
      ? <Link href={`${projectHref(project_id)}/studio?experiment=${encodeURIComponent(experiment_id)}`}>{experiment.data?.title || `Experiment ${experiment_id.slice(-8)}`}</Link>
      : 'Project research'}</h3>
    <ul className={styles.runList}>{runs.map(run => <RunRow key={run.id} project_id={project_id} run={run} />)}</ul>
  </section>
}

export function TrackerScreen({ project_id }: { project_id: string }) {
  const [status, setStatus] = useState(''), [kind, setKind] = useState('')
  const workspace = useWorkspace(project_id)
  const runs = useRuns(project_id, { status: status || undefined, kind: kind || undefined })
  const groups = new Map<string, Run[]>()
  for (const run of [...runs.items].filter(run => run.project_id === project_id).reverse()) {
    const key = 'experiment_id' in run.input ? run.input.experiment_id : ''
    groups.set(key, [...(groups.get(key) ?? []), run])
  }
  return <div className={styles.tracker}>
    <header className={styles.pageHeading}><h1>Tracker</h1><p>Follow the work from investigation to saved results.</p></header>
    <div className={styles.workflow} aria-label="Research workflow">
      <div><strong>Research</strong><span>Question, literature &amp; evidence</span></div>
      <span aria-hidden="true">→</span>
      <div><strong>Analysis</strong><span>Experiment, inputs &amp; measurements</span></div>
      <span aria-hidden="true">→</span>
      <div><strong>Report</strong><span>Evidence-backed findings</span></div>
    </div>
    <section className={styles.active}>
      <div className={styles.sectionHeading}><h2>Active work</h2><span>Live project state</span></div>
      <ErrorNotice error={workspace.error} />
      {workspace.data?.active_run_ids.length ? <ul className={styles.runList}>{workspace.data.active_run_ids.map(id => <ActiveRun key={id} project_id={project_id} id={id} />)}</ul>
        : <div className={styles.empty}><p>No runs are active.</p><Link href={`${projectHref(project_id)}/studio`}>Open an experiment</Link><span> or direct research in Chat.</span></div>}
    </section>
    <section>
      <div className={styles.sectionHeading}><h2>Run history</h2><span>{runs.items.length} loaded{runs.has_next_page ? ' · more available' : ''}</span></div>
      <div className={styles.filters}>
        <label>Status<select value={status} onChange={e => setStatus(e.target.value)}><option value="">All statuses</option>{Object.entries(LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>Work type<select value={kind} onChange={e => setKind(e.target.value)}><option value="">All types</option>{Object.entries(KINDS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      </div>
      <ErrorNotice error={runs.error} />
      {runs.is_loading && <p className={styles.loading} aria-busy="true">Loading run history…</p>}
      {!runs.is_loading && !runs.error && !runs.items.length && <p className={styles.empty}>No runs match these filters. Start research in Chat or analysis in Experiments.</p>}
      {[...groups].map(([id, rows]) => <HistoryGroup key={id} project_id={project_id} experiment_id={id || undefined} runs={rows} />)}
      <PageMore has_more={runs.has_next_page} loading={runs.is_fetching_next_page} load={runs.load_next_page} />
      <p className={styles.qualification}>These are execution states. A completed run does not establish a scientific conclusion.</p>
    </section>
  </div>
}
