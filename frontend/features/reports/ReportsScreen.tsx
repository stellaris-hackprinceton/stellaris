'use client'
import Link from 'next/link'
import { useState } from 'react'
import type { ID } from '@/contracts/api'
import type { ReportRequest } from '@/contracts/requests'
import { terminal, useCapabilities, useExperiment, useProject, useRun, useRunResults, useWorkspace } from '@/lib/queries'
import { useCatalogView } from '@/lib/queries/views'
import { Button, ErrorNotice, Field, Skeleton, TextInput, describeError } from '@/components/ui'
import { hrefs } from '@/components/shell/hrefs'
import { ReportCard } from './ReportCard'
import { DeskGrid } from '@/components/ui/Desk'
import { ReportComposer, type ComposerContext, type ComposerDraft } from './ReportComposer'
import styles from './reports.module.css'

const PAGE = 24

export function ReportsScreen({ project_id, compose = false, experiment, evidence_run }: { project_id: ID, compose?: boolean, experiment?: ID, evidence_run?: ID }) {
  const capabilities = useCapabilities(), project = useProject(project_id)
  const context: ComposerContext | undefined = compose && (experiment || evidence_run) ? { experiment, evidence_run } : undefined
  const [open, setOpen] = useState(compose)
  const [collapsed, setCollapsed] = useState(false)
  const [draft, setDraft] = useState<{ key: number, initial?: ComposerDraft, context?: ComposerContext }>({ key: 0, context })
  const [accepted, setAccepted] = useState<ID[]>([])
  const [search, setSearch] = useState(''), [q, setQ] = useState('')
  const contextExperiment = useExperiment(project_id, experiment)
  const generation = capabilities.data?.features.markdown_reports === true
  const archived = project.data?.status === 'archived'

  function openComposer() { setOpen(true); setCollapsed(false) }
  function generateAgain(input: ReportRequest) {
    // A deliberate new draft with the recorded selections; submission requires a new command key.
    setDraft(d => ({ key: d.key + 1, initial: { title: input.title, experiment_id: input.experiment_id, evidence_run_ids: input.evidence_run_ids, source_ids: input.source_ids } }))
    openComposer()
  }

  return <div className={styles.screen}>
    <header className={styles.header}>
      <div><h1>Reports</h1><p>Reports summarize selected saved evidence.</p></div>
      <Button variant="primary" onClick={openComposer} disabled={open && !collapsed}>+ Generate report</Button>
    </header>
    {experiment && <p><span className={styles.chip}>Experiment context: {contextExperiment.data?.project_id === project_id ? contextExperiment.data.title : contextExperiment.error ? 'unavailable' : '…'}</span> <span className={styles.muted}>Context preselects the composer; the library below is not filtered.</span></p>}
    {open && <div hidden={collapsed}>
      <ReportComposer key={draft.key} project_id={project_id} context={draft.context} initial={draft.initial}
        onAccepted={run => { setAccepted(ids => [run.id, ...ids.filter(id => id !== run.id)]); setOpen(false); setCollapsed(false); setDraft(previous => ({ key: previous.key + 1 })) }}
        onClose={() => { setOpen(false); setCollapsed(false); setDraft(previous => ({ key: previous.key + 1 })) }} onCollapse={() => setCollapsed(true)} />
    </div>}
    {open && collapsed && <p className={styles.muted}>The report draft is hidden and kept while this page stays open. <Button onClick={() => setCollapsed(false)}>Show draft</Button></p>}
    {!open && capabilities.data && !generation && <p role="note">Report generation is unavailable on this backend. Saved reports remain readable.</p>}
    {!open && archived && <p role="note">Restore project to add or generate material. Saved reports remain readable.</p>}
    <ReportActivity project_id={project_id} accepted={accepted} onDismiss={id => setAccepted(ids => ids.filter(x => x !== id))} onGenerateAgain={generateAgain} />
    <form className={styles.search} role="search" onSubmit={e => { e.preventDefault(); setQ(search.trim()) }}>
      <Field label="Search report names"><TextInput type="search" value={search} onChange={e => setSearch(e.target.value)} /></Field>
      <Button type="submit">Search</Button>
      {q && <Button onClick={() => { setSearch(''); setQ('') }}>Clear search</Button>}
    </form>
    <ReportLibrary project_id={project_id} q={q} />
  </div>
}

function ReportLibrary({ project_id, q }: { project_id: ID, q: string }) {
  const list = useCatalogView(project_id, { artifact_kinds: ['report'], q, sort: 'created_at', order: 'desc' }, PAGE)
  const workspace = useWorkspace(project_id)
  if (list.unsupported) {
    const latest = workspace.data?.latest_report_artifact_id
    return <section aria-label="Saved reports">
      <p role="note">The full report library needs the backend workspace views extension, which this backend does not advertise. Existing report readers remain available.</p>
      {latest ? <DeskGrid><li><ReportCard project_id={project_id} artifact_id={latest} /></li></DeskGrid> : workspace.data ? <p>No latest report is recorded for this project.</p> : null}
    </section>
  }
  if (list.capability_error) return <ErrorNotice {...describeError(list.capability_error, 'Backend capabilities could not be loaded')} />
  if (list.is_loading || list.capability_pending) return <div aria-busy="true"><DeskGrid>{[0, 1, 2].map(i => <li key={i} className={styles.card}><Skeleton height="1.25rem" /><Skeleton width="60%" /></li>)}</DeskGrid></div>
  if (list.error && !list.items.length) return <ErrorNotice {...describeError(list.error, 'Saved reports could not be loaded')} action={<Button onClick={() => void list.refetch()}>Retry</Button>} />
  if (!list.items.length) return <p>{q ? 'No report names match this search.' : 'No reports saved yet. Generate one from recorded experiment analysis.'}</p>
  return <section aria-label="Saved reports">
    <DeskGrid>
      {list.items.map(file => <li key={file.id}>{file.origin?.type === 'artifact' ? <ReportCard project_id={project_id} artifact_id={file.origin.id} /> : <article className={styles.card}><p className={styles.cardTitle}>Report unavailable</p></article>}</li>)}
    </DeskGrid>
    {list.is_next_page_error && <ErrorNotice {...describeError(list.error, 'More reports could not be loaded')} action={<Button onClick={() => void list.load_next_page()}>Retry</Button>} />}
    {list.has_next_page && !list.is_next_page_error && <p><Button onClick={() => void list.load_next_page()} pending={list.is_fetching_next_page}>Load more</Button></p>}
  </section>
}

function ReportActivity({ project_id, accepted, onDismiss, onGenerateAgain }: { project_id: ID, accepted: ID[], onDismiss: (id: ID) => void, onGenerateAgain: (input: ReportRequest) => void }) {
  const workspace = useWorkspace(project_id)
  const active = (workspace.data?.active_run_ids ?? []).filter(id => !accepted.includes(id))
  if (!accepted.length && !active.length) return null
  return <section aria-label="Report generation activity" aria-live="polite" className={styles.form}>
    {accepted.map(id => <RunNotice key={id} project_id={project_id} run_id={id} accepted onDismiss={() => onDismiss(id)} onGenerateAgain={onGenerateAgain} />)}
    {active.map(id => <RunNotice key={id} project_id={project_id} run_id={id} onGenerateAgain={onGenerateAgain} />)}
  </section>
}

function RunNotice({ project_id, run_id, accepted = false, onDismiss, onGenerateAgain }: { project_id: ID, run_id: ID, accepted?: boolean, onDismiss?: () => void, onGenerateAgain: (input: ReportRequest) => void }) {
  const query = useRun(project_id, run_id)
  const run = query.data
  const results = useRunResults(project_id, run?.status === 'succeeded' ? run.id : null)
  if (!run) return accepted ? <div className={styles.notice}><p>Report generation accepted.</p><Link href={hrefs.run(project_id, run_id)}>Open run</Link></div> : null
  if (run.input.kind !== 'report') return null
  const input = run.input
  const runLink = <Link href={hrefs.run(project_id, run.id)}>Open run</Link>
  const dismiss = onDismiss && terminal(run) ? <Button onClick={onDismiss}>Dismiss</Button> : null
  if (run.status === 'succeeded') {
    const reportId = results.data?.report_artifact_id ?? null
    if (results.error) return <div className={styles.notice}><p>Report generation finished, but its saved outputs could not be loaded.</p><Button onClick={() => void results.refetch()}>Retry</Button>{runLink}{dismiss}</div>
    if (!results.data) return <div className={styles.notice}><p>Report generation finished. Checking saved output…</p>{runLink}</div>
    return reportId
      ? <div className={styles.notice}><p><strong>Report saved</strong> · “{input.title}”</p><Link href={hrefs.report(project_id, reportId)}>Open report</Link>{runLink}{dismiss}</div>
      : <div className={styles.notice}><p><strong>Report output unavailable</strong> · the run succeeded but no report artifact is recorded.</p>{runLink}{dismiss}</div>
  }
  if (run.status === 'failed' || run.status === 'cancelled') return <div className={styles.notice}>
    <p><strong>Report generation {run.status}</strong>{run.error ? ` · ${run.error.message}` : ''}</p>{runLink}
    <Button onClick={() => onGenerateAgain(input)}>Generate again</Button>{dismiss}
  </div>
  const fraction = run.progress.fraction
  return <div className={styles.notice}>
    <p><strong>{accepted ? 'Report generation accepted' : 'Report generation'}</strong> · {run.status === 'awaiting_approval' ? 'Awaiting approval' : run.status.replaceAll('_', ' ')}{fraction != null ? ` · ${Math.round(fraction * 100)}%` : ''}{run.progress.message ? ` · ${run.progress.message}` : run.phase ? ` · ${run.phase}` : ''}</p>
    {run.status === 'awaiting_approval' ? <Link href={hrefs.run(project_id, run.id)}>Review approval</Link> : runLink}
    {query.error && <span className={styles.muted}>Status may be stale; the run record could not be refreshed.</span>}
  </div>
}
