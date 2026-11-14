'use client'

import Link from 'next/link'
import { artifactContentUrl } from '@/lib/api'
import { useArtifact, useExperiment, useRun } from '@/lib/queries'
import { Button, ErrorNotice, describeError } from '@/components/ui'
import { hrefs } from '@/components/shell/hrefs'
import { ArtifactPreview } from '@/features/workspace/preview'
import styles from './reports.module.css'

export { ReportCard } from './ReportCard'
export { ReportComposer } from './ReportComposer'
export type { ComposerContext, ComposerDraft } from './ReportComposer'
export { ReportsScreen } from './ReportsScreen'

/** Saved report reader. Uses the existing safe Markdown preview with its 256 KiB truncation notice. */
export function ReportScreen({ project_id, artifact_id }: { project_id: string, artifact_id: string }) {
  const query = useArtifact(project_id, artifact_id)
  const artifact = query.data
  const run = useRun(project_id, artifact?.kind === 'report' ? artifact.run_id : null)
  const recorded = run.data?.input.kind === 'report' ? run.data.input : null
  const experimentId = artifact?.experiment_id ?? recorded?.experiment_id ?? null
  const experiment = useExperiment(project_id, experimentId)
  const back = <Link href={hrefs.reports(project_id)}>Back to Reports</Link>
  if (query.error && !artifact) return <main className={styles.reader}>{back}<h1>Report unavailable</h1><ErrorNotice {...describeError(query.error, 'This report could not be loaded')} action={<Button onClick={() => void query.refetch()}>Retry</Button>} /></main>
  if (!artifact) return <main className={styles.reader} aria-busy="true">{back}<p>Loading saved report…</p></main>
  if (artifact.project_id !== project_id || artifact.kind !== 'report' || !['text/markdown', 'text/plain'].includes(artifact.mime_type.split(';')[0].trim().toLowerCase())) {
    return <main className={styles.reader}>{back}<h1>Report unavailable</h1><p>This file is not a supported Markdown report in this project.</p></main>
  }
  return <main className={styles.reader}>
    {back}
    <h1>{recorded?.title?.trim() || artifact.filename}</h1>
    <p className={styles.meta}>Saved {new Date(artifact.created_at).toLocaleString()}{experimentId && experiment.data ? <> · Experiment: <Link href={hrefs.studio(project_id, experimentId)}>{experiment.data.title}</Link></> : null}</p>
    <div className={styles.actions}>
      <a href={artifactContentUrl(project_id, artifact_id, 'attachment')} download={artifact.filename}>Download Markdown</a>
      <Link href={hrefs.artifact(project_id, artifact_id)}>Evidence and provenance</Link>
      {artifact.run_id && <Link href={hrefs.run(project_id, artifact.run_id)}>Report generation run</Link>}
    </div>
    <p className={styles.muted}>Reports are immutable. Generating another report creates a separate file. A saved report documents selected evidence; it does not confirm the experiment or its hypothesis.</p>
    <div className={styles.document}><ArtifactPreview project_id={project_id} artifact={artifact} /></div>
  </main>
}
