'use client'
import Link from 'next/link'
import { useRef, useState } from 'react'
import type { ID, Run } from '@/contracts/api'
import type { ReportRequest } from '@/contracts/requests'
import { ApiError } from '@/lib/api'
import { terminal, useCapabilities, useExperiment, useExperiments, useProject, useRun, useRuns, useSources, useStartRun } from '@/lib/queries'
import { Button, ErrorNotice, Field, Select, StatusBadge, TextInput, describeError, newCommandKey } from '@/components/ui'
import { hrefs } from '@/components/shell/hrefs'
import styles from './reports.module.css'

const MAX_RUNS = 20, MAX_SOURCES = 100, MAX_TITLE = 200
const RETRIEVAL: Record<string, string> = { metadata_only: 'Metadata only', abstract_retrieved: 'Abstract retrieved', full_text_retrieved: 'Full text retrieved', failed: 'Retrieval failed' }
const STATUS: Record<Run['status'], string> = { queued: 'Queued', running: 'Running', awaiting_approval: 'Awaiting approval', cancelling: 'Cancelling', succeeded: 'Succeeded', failed: 'Failed', cancelled: 'Cancelled' }

export type ComposerDraft = { title?: string, experiment_id?: ID, evidence_run_ids?: ID[], source_ids?: ID[] }
export type ComposerContext = { experiment?: ID, evidence_run?: ID }

/** Acceptance is uncertain unless the server definitively rejected the request. */
function definitiveRejection(error: unknown) {
  return error instanceof ApiError && error.status >= 400 && error.status < 500 && ![408, 429].includes(error.status) && error.code !== 'COMMAND_IN_PROGRESS'
}

export function ReportComposer({ project_id, context, initial, onAccepted, onClose, onCollapse }: {
  project_id: ID, context?: ComposerContext, initial?: ComposerDraft,
  onAccepted?: (run: Run) => void, onClose?: () => void, onCollapse?: () => void,
}) {
  const capabilities = useCapabilities(), project = useProject(project_id)
  const experiments = useExperiments(project_id), sources = useSources(project_id)
  const [title, setTitle] = useState(initial?.title ?? '')
  const [experimentId, setExperimentId] = useState(initial?.experiment_id ?? '')
  const [evidence, setEvidence] = useState<ID[]>(initial?.evidence_run_ids ?? [])
  const [references, setReferences] = useState<ID[]>(initial?.source_ids ?? [])
  const [pendingExperiment, setPendingExperiment] = useState<string | null>(null)
  const [confirmClose, setConfirmClose] = useState(false)
  const [touched, setTouched] = useState(false)
  const runs = useRuns(project_id, { kind: 'analysis', experiment_id: experimentId || undefined })
  const start = useStartRun(project_id)
  const command = useRef<{ body: ReportRequest, key: string } | null>(null)
  const [failure, setFailure] = useState<{ error: unknown, definitive: boolean } | null>(null)

  // Contextual entry: validate supplied IDs against this project before preselecting anything.
  const ctxExperiment = useExperiment(project_id, context?.experiment)
  const ctxRun = useRun(project_id, context?.evidence_run)
  const [contextApplied, setContextApplied] = useState(!context?.experiment && !context?.evidence_run)
  let contextError: string | null = null, contextInfo: string | null = null
  if (context?.evidence_run && !context.experiment) contextError = 'The linked run was supplied without its experiment. Choose an experiment below.'
  else if (context?.experiment) {
    if (ctxExperiment.error || (ctxExperiment.data && ctxExperiment.data.project_id !== project_id)) contextError = 'The linked experiment is not available in this project. Choose an experiment below.'
    else if (context.evidence_run && (ctxRun.error || (ctxRun.data && ctxRun.data.project_id !== project_id))) contextError = 'The linked analysis run is not available in this project.'
    else if (ctxRun.data && ctxRun.data.input.kind !== 'analysis') contextError = 'The linked run is not an analysis run and cannot be report evidence.'
    else if (ctxRun.data && ctxRun.data.input.kind === 'analysis' && ctxRun.data.input.experiment_id !== context.experiment) contextError = 'The linked run belongs to a different experiment. It was not selected.'
    else if (ctxRun.data && !terminal(ctxRun.data)) contextInfo = 'The linked analysis run is still active. It must finish before it can be included.'
  }
  const contextResolved = !context?.experiment || !!contextError || (!!ctxExperiment.data && (!context.evidence_run || !!ctxRun.data))
  if (!contextApplied && contextResolved) {
    setContextApplied(true)
    if (!contextError && context?.experiment && ctxExperiment.data?.project_id === project_id) {
      setExperimentId(context.experiment)
      if (context.evidence_run && ctxRun.data && terminal(ctxRun.data)) setEvidence([ctxRun.data.id])
    }
  }

  const features = capabilities.data?.features
  const archived = project.data?.status === 'archived'
  const uncertain = !!failure && !failure.definitive
  const locked = start.isPending || uncertain || !!failure?.definitive
  const trimmed = title.trim()
  const titleError = !trimmed ? 'A report title is required.' : trimmed.length > MAX_TITLE ? `Use at most ${MAX_TITLE} characters.` : null
  const experimentRuns = runs.items.filter(r => r.input.kind === 'analysis' && r.input.experiment_id === experimentId)
  const experimentTitle = experiments.items.find(e => e.id === experimentId)?.title ?? (ctxExperiment.data?.id === experimentId ? ctxExperiment.data.title : null)
  const dirty = !!title.trim() || !!experimentId || evidence.length > 0 || references.length > 0
  const canSubmit = !archived && features?.markdown_reports === true && !titleError && !!experimentId && evidence.length > 0 && evidence.length <= MAX_RUNS && references.length <= MAX_SOURCES

  function chooseExperiment(id: string) {
    if (id === experimentId) return
    if (evidence.length) { setPendingExperiment(id); return }
    setExperimentId(id)
  }
  function toggle(list: ID[], id: ID, max: number) { return list.includes(id) ? list.filter(v => v !== id) : list.length >= max ? list : [...list, id] }
  function clear() { setTitle(''); setExperimentId(''); setEvidence([]); setReferences([]); setTouched(false); setPendingExperiment(null) }
  async function submit() {
    setTouched(true)
    if (!command.current) {
      if (!canSubmit) return
      command.current = { body: { kind: 'report', experiment_id: experimentId, evidence_run_ids: [...new Set(evidence)], source_ids: [...new Set(references)], title: trimmed, format: 'markdown' }, key: newCommandKey() }
    }
    setFailure(null)
    try {
      const response = await start.mutateAsync({ body: command.current.body, idempotency_key: command.current.key })
      command.current = null
      clear()
      onAccepted?.(response.data)
    } catch (error) {
      setFailure({ error, definitive: definitiveRejection(error) })
    }
  }
  function editRequest() { command.current = null; setFailure(null); start.reset() }
  function requestClose() { if (dirty && !locked) setConfirmClose(true); else if (!locked) onClose?.() }

  return <section className={styles.composer} aria-labelledby="report-composer-heading">
    <div className={styles.composerHead}>
      <h2 id="report-composer-heading">Generate report</h2>
      <div className={styles.actions}>
        {onCollapse && <Button onClick={onCollapse}>Hide composer</Button>}
        {onClose && <Button onClick={requestClose} disabled={locked}>Close</Button>}
      </div>
    </div>
    {confirmClose && <div className={styles.confirm} role="alert">
      <p>Discard this report draft? Your title and selections will be lost.</p>
      <div className={styles.actions}><Button variant="danger" onClick={() => { setConfirmClose(false); clear(); onClose?.() }}>Discard draft</Button><Button onClick={() => setConfirmClose(false)}>Keep editing</Button></div>
    </div>}
    <p className={styles.muted}>Reports assemble Markdown from saved evidence. Generating a report establishes document creation, not confirmation of the experiment or its hypothesis.</p>
    {capabilities.data && features?.markdown_reports !== true && <p role="note">Markdown report generation is unavailable on this backend. Existing reports remain readable.</p>}
    {archived && <p role="note">Restore project to add or generate material.</p>}
    {contextError && <ErrorNotice title="Linked context not applied" message={contextError} />}
    {contextInfo && <p role="note">{contextInfo}</p>}
    {!contextApplied && <p role="status">Checking the linked experiment…</p>}
    <form className={styles.form} onSubmit={e => { e.preventDefault(); void submit() }} noValidate>
      <fieldset className={styles.fieldset} disabled={locked}>
        <legend>Report</legend>
        <Field label="Report title" hint={`${trimmed.length}/${MAX_TITLE} characters`} error={touched ? titleError : null}>
          <TextInput value={title} maxLength={MAX_TITLE + 20} onChange={e => setTitle(e.target.value)} required />
        </Field>
        <Field label="Experiment" error={touched && !experimentId ? 'Choose an experiment.' : null}>
          <Select value={experimentId} onChange={e => chooseExperiment(e.target.value)} required>
            <option value="">Choose an experiment</option>
            {experimentId && !experiments.items.some(e => e.id === experimentId) && <option value={experimentId}>{experimentTitle ?? 'Linked experiment'}</option>}
            {experiments.items.map(e => <option key={e.id} value={e.id}>{e.title}</option>)}
          </Select>
        </Field>
        {experiments.error && <ErrorNotice {...describeError(experiments.error, 'Experiments could not be loaded')} action={<Button onClick={() => void experiments.refetch()}>Retry</Button>} />}
        {experiments.has_next_page && <div><Button onClick={() => void experiments.load_next_page()} pending={experiments.is_fetching_next_page}>Load more experiments</Button></div>}
        {pendingExperiment !== null && <div className={styles.confirm} role="alert">
          <p>Changing the experiment clears the {evidence.length} selected analysis run{evidence.length === 1 ? '' : 's'}. Title and literature selections are kept.</p>
          <div className={styles.actions}><Button variant="danger" onClick={() => { setEvidence([]); setExperimentId(pendingExperiment); setPendingExperiment(null) }}>Change experiment</Button><Button onClick={() => setPendingExperiment(null)}>Keep current experiment</Button></div>
        </div>}
      </fieldset>

      <fieldset className={styles.fieldset} disabled={locked || !experimentId}>
        <legend>Analysis runs to include ({evidence.length} of max {MAX_RUNS} selected)</legend>
        {!experimentId ? <p className={styles.muted}>Choose an experiment to list its analysis runs.</p> : <>
          <p className={styles.muted}>Failed or cancelled runs can supply partial evidence; their limitations are retained in the report. The backend decides whether the selected evidence is valid.</p>
          {runs.error && <ErrorNotice {...describeError(runs.error, 'Analysis runs could not be loaded')} action={<Button onClick={() => void runs.refetch()}>Retry</Button>} />}
          {runs.is_loading ? <p role="status">Loading analysis runs…</p> : !experimentRuns.length && !runs.error ? <p>No analysis runs are recorded for this experiment in the loaded history.</p> : null}
          <div className={styles.choices}>
            {experimentRuns.map(r => {
              const done = terminal(r), checked = evidence.includes(r.id)
              const disabled = !done || (!checked && evidence.length >= MAX_RUNS)
              return <label key={r.id} className={styles.choice} data-disabled={disabled}>
                <input type="checkbox" checked={checked} disabled={disabled} onChange={() => setEvidence(toggle(evidence, r.id, MAX_RUNS))} />
                <span>
                  <strong>{new Date(r.started_at ?? r.created_at).toLocaleString()}</strong> · run …{r.id.slice(-8)}<br />
                  <StatusBadge tone={r.status === 'failed' ? 'error' : r.status === 'cancelled' ? 'warning' : r.status === 'succeeded' ? 'success' : 'info'}>{r.status === 'failed' || r.status === 'cancelled' ? `Partial evidence · ${r.status}` : STATUS[r.status]}</StatusBadge>
                  {r.result_summary && <><br /><span className={styles.muted}>{r.result_summary}</span></>}
                  {!done && <><br /><span className={styles.muted}>Must finish before it can be included.</span></>}
                </span>
              </label>
            })}
          </div>
          {runs.has_next_page && <div><Button onClick={() => void runs.load_next_page()} pending={runs.is_fetching_next_page}>Load more runs</Button></div>}
          {evidence.length >= MAX_RUNS && <p role="note">The {MAX_RUNS}-run limit is reached. Clear a selection to choose another.</p>}
        </>}
      </fieldset>

      <fieldset className={styles.fieldset} disabled={locked}>
        <legend>Saved literature sources ({references.length} of max {MAX_SOURCES} selected, optional)</legend>
        {sources.error && <ErrorNotice {...describeError(sources.error, 'Sources could not be loaded')} action={<Button onClick={() => void sources.refetch()}>Retry</Button>} />}
        {sources.is_loading ? <p role="status">Loading sources…</p> : !sources.items.length && !sources.error ? <p className={styles.muted}>No literature sources are saved.</p> : null}
        <div className={styles.choices}>
          {sources.items.map(s => {
            const checked = references.includes(s.id), disabled = !checked && references.length >= MAX_SOURCES
            return <label key={s.id} className={styles.choice} data-disabled={disabled}>
              <input type="checkbox" checked={checked} disabled={disabled} onChange={() => setReferences(toggle(references, s.id, MAX_SOURCES))} />
              <span>{s.title}<br /><span className={styles.muted}>{RETRIEVAL[s.retrieval_status] ?? s.retrieval_status}{s.full_text?.truncated ? ' · Partial extraction' : ''}</span></span>
            </label>
          })}
        </div>
        {sources.has_next_page && <div><Button onClick={() => void sources.load_next_page()} pending={sources.is_fetching_next_page}>Load more sources</Button></div>}
      </fieldset>

      <div className={styles.summary}>
        <p className={styles.muted} aria-live="polite">Experiment: {experimentId ? experimentTitle ?? 'selected' : 'none'} · {evidence.length} analysis run{evidence.length === 1 ? '' : 's'} · {references.length} source{references.length === 1 ? '' : 's'}</p>
        <Button type="submit" variant="primary" pending={start.isPending} disabled={!canSubmit || !!failure?.definitive}>
          {uncertain ? 'Retry the same submission' : 'Generate Markdown report'}
        </Button>
      </div>
    </form>
    {failure && (failure.definitive
      ? <ErrorNotice {...describeError(failure.error, 'Report request rejected')} action={<Button onClick={editRequest}>Edit request</Button>} />
      : <ErrorNotice {...describeError(failure.error, 'Submission outcome unknown')} message="The request may or may not have been accepted. Retrying sends the identical request with the same command key, so it cannot create a duplicate run. The form is locked until acceptance is resolved."
          action={<div className={styles.actions}><Button onClick={() => void submit()} pending={start.isPending}>Retry the same submission</Button><Link href={hrefs.view(project_id, 'runs')}>Check Activity</Link></div>} />)}
  </section>
}
