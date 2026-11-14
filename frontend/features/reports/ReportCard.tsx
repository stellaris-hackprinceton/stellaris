'use client'
import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { Artifact, ID } from '@/contracts/api'
import { artifactContentUrl, readText } from '@/lib/api'
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
  const previewRef = useRef<HTMLDivElement | null>(null)
  const [previewVisible, setPreviewVisible] = useState(false)
  const artifact = useArtifact(project_id, supplied?.id ?? artifact_id)
  const a = supplied ?? artifact.data
  const run = useRun(project_id, a?.run_id)
  const recorded = run.data?.input.kind === 'report' ? run.data.input : null
  const experimentId = a?.experiment_id ?? recorded?.experiment_id ?? null
  const experiment = useExperiment(project_id, experimentId)
  useEffect(() => {
    const element = previewRef.current
    if (!element || previewVisible) return
    if (typeof IntersectionObserver === 'undefined') {
      const frame = requestAnimationFrame(() => setPreviewVisible(true))
      return () => cancelAnimationFrame(frame)
    }
    const observer = new IntersectionObserver(entries => { if (entries.some(entry => entry.isIntersecting)) { setPreviewVisible(true); observer.disconnect() } }, { rootMargin: '200px' })
    observer.observe(element)
    return () => observer.disconnect()
  }, [previewVisible, a?.id])
  const excerpt = useQuery({
    queryKey: ['project', project_id, 'report-excerpt', a?.id, a?.sha256],
    queryFn: ({ signal }) => readText(artifactContentUrl(project_id, a!.id, 'inline'), signal),
    enabled: previewVisible && a?.project_id === project_id && a?.kind === 'report', retry: false,
  })
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
    <div ref={previewRef} className={styles.excerpt} aria-label="Saved report excerpt">
      {!previewVisible || excerpt.isPending ? <span className={styles.meta}>Loading saved excerpt…</span>
        : excerpt.error ? <span className={styles.meta}>Saved excerpt unavailable.</span>
        : <p>{excerpt.data.text.replace(/```[\s\S]*?```/g, ' ').replace(/!\[[^\]]*\]\([^)]*\)/g, ' ').replace(/\[([^\]]*)\]\([^)]*\)/g, '$1').replace(/[#>*_`~|]/g, '').replace(/\s+/g, ' ').trim().slice(0, 240) || <span className={styles.meta}>No readable text in the saved excerpt.</span>}{excerpt.data.truncated && <span className={styles.meta}> Excerpt from the first 256 KiB.</span>}</p>}
    </div>
    {experimentId && experiment.data?.project_id === project_id && <p className={styles.meta}>Experiment: <Link href={hrefs.studio(project_id, experimentId)}>{experimentName ?? experiment.data.title}</Link></p>}
    <div><StatusBadge tone="neutral">Generated report</StatusBadge></div>
    <div className={styles.actions}>
      <Link href={hrefs.report(project_id, a.id)}>Open report</Link>
      <a href={artifactContentUrl(project_id, a.id, 'attachment')} download={a.filename}>Download Markdown</a>
      {onInspect ? <Button onClick={onInspect}>Evidence and provenance</Button> : <Link href={hrefs.artifact(project_id, a.id)}>Evidence and provenance</Link>}
    </div>
  </article>
}
