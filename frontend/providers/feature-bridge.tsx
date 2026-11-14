'use client'

import Link from 'next/link'
import type { ComponentType, ReactNode } from 'react'
import styles from '@/features/execution/sol.module.css'

// Sole integration point for Claude exports. Replace null with static imported
// components here once their owners publish the agreed interfaces.
type ProjectProps = { project_id: string }
export type ClaudeFeatures = {
  ProjectsScreen: ComponentType | null,
  ProjectShell: ComponentType<ProjectProps & { children: ReactNode }> | null,
  ResearchScreen: ComponentType<ProjectProps> | null,
  StudioScreen: ComponentType<ProjectProps> | null,
  ResultsPane: ComponentType<ProjectProps & { run_id: string }> | null,
}
const features: ClaudeFeatures = { ProjectsScreen: null, ProjectShell: null, ResearchScreen: null, StudioScreen: null, ResultsPane: null }
function Pending({ title, owner }: { title: string, owner: string }) {
  return <section className={styles.screen}><h1>{title}</h1><p>Awaiting Claude {owner} implementation.</p><p>This boundary contains no sample research or fabricated results.</p><a href="/docs/frontend-implementation-spec.md">Read the shared implementation specification</a></section>
}
export function ProjectsSlot() { const Screen = features.ProjectsScreen; return Screen ? <Screen /> : <Pending title="Research projects" owner="A" /> }
export function ResearchSlot(props: ProjectProps) { const Screen = features.ResearchScreen; return Screen ? <Screen {...props} /> : <Pending title="Research" owner="A" /> }
export function StudioSlot(props: ProjectProps) { const Screen = features.StudioScreen; return Screen ? <Screen {...props} /> : <Pending title="Experiment Studio" owner="B" /> }
export function ResultsSlot(props: ProjectProps & { run_id: string }) { const Screen = features.ResultsPane; return Screen ? <Screen {...props} /> : <Pending title="Scientific results inspection" owner="B" /> }
export function ProjectShellSlot({ children, project_id }: ProjectProps & { children: ReactNode }) {
  const Shell = features.ProjectShell
  if (Shell) return <Shell project_id={project_id}>{children}</Shell>
  const base = `/projects/${encodeURIComponent(project_id)}`
  return <div className={styles.frame}><nav className={styles.nav} aria-label="Project navigation"><Link href="/projects">Projects</Link><Link href={`${base}/research`}>Research</Link><Link href={`${base}/studio`}>Studio</Link><Link href={`${base}/runs`}>Runs</Link><Link href={`${base}/workspace`}>Workspace</Link></nav><p className={styles.muted}>Shared shell and chat await Claude A.</p>{children}</div>
}
