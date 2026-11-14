import { Suspense, type ReactNode } from 'react'
import { ProjectRuntime } from '@/providers/project-runtime'
async function ProjectLayoutContent({ params, children }: { params: Promise<{ projectId: string }>, children: ReactNode }) {
  const { projectId } = await params
  return <ProjectRuntime key={projectId} project_id={projectId}>{children}</ProjectRuntime>
}
export default function ProjectLayout(props: { params: Promise<{ projectId: string }>, children: ReactNode }) {
  return <Suspense fallback={<p>Opening project…</p>}><ProjectLayoutContent {...props} /></Suspense>
}
