'use client'
import Link from 'next/link'
import type { Artifact, ID } from '@/contracts/api'
import { artifactContentUrl } from '@/lib/api'
import { useArtifact, useExperiment, useRun } from '@/lib/queries'
import { Button, Skeleton, StatusBadge } from '@/components/ui'
import { hrefs } from '@/components/shell/hrefs'
import styles from './reports.module.css'

/**
 * Shared report card (Writing widget, Reports library, mixed Materials views).
 * Title is the artifact filename unless the generating report run recorded a title.
 * An unknown experiment is omitted, never inferred.
 */
export function ReportCard({ project_id, artifact: supplied, artifact_id, experimentName, onInspect }: { project_id: ID, artifact?: Artifact, artifact_id?: ID, experimentName?: string, onInspect?: () => void }) {
  const artifact = useArtifact(project_id, supplied?.id ?? artifact_id)
  const a = supplied ?? artifact.data
  const run = useRun(project_id, a?.run_id)
  const recorded = run.data?.input.kind === 'report' ? run.data.input : null
  const experimentId = a?.experiment_id ?? recorded?.experiment_id ?? null
  const experiment = useExperiment(project_id, experimentId)
  if (artifact.error && !a) return <article className={styles.card}>
    <p className={styles.cardTitle}>Report unavailable</p>
    <p className={styles.meta}>This saved report could not be loaded.</p>
    <div className={styles.actions}><Button onClick={() => void artifact.refetch()}>Retry</Button></div>
  </article>
  if (!a) return <article className={styles.card} aria-busy="true"><Skeleton height="1.25rem" /><Skeleton width="60%" /><Skeleton width="40%" /></article>
  if (a.project_id !== project_id || a.kind !== 'report') return <article className={styles.card}><p className={styles.cardTitle}>Report unavailable</p><p className={styles.meta}>This file is not a report in this project.</p></article>
  const title = recorded?.title?.trim() || a.filename
  return <article className={styles.card}>
    <h3 className={styles.cardTitle}><Link href={hrefs.report(project_id, a.id)}>{title}</Link></h3>
    <p className={styles.meta}>Saved {new Date(a.created_at).toLocaleString()}</p>
    {experimentId && experiment.data?.project_id === project_id && <p className={styles.meta}>Experiment: <Link href={hrefs.studio(project_id, experimentId)}>{experimentName ?? experiment.data.title}</Link></p>}
    <div><StatusBadge tone="neutral">Generated report</StatusBadge></div>
    <div className={styles.actions}>
      <Link href={hrefs.report(project_id, a.id)}>Open report</Link>
      <a href={artifactContentUrl(project_id, a.id, 'attachment')} download={a.filename}>Download Markdown</a>
      {onInspect ? <Button onClick={onInspect}>Evidence and provenance</Button> : <Link href={hrefs.artifact(project_id, a.id)}>Evidence and provenance</Link>}
    </div>
  </article>
}
