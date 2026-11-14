import { Suspense } from 'react'
import { redirect } from 'next/navigation'
import LoadingProjectView from './loading'

type Props = { params: Promise<{ projectId: string }> }

export default function ProjectPage({ params }: Props) {
  return <Suspense fallback={<LoadingProjectView />}><ProjectRedirect params={params} /></Suspense>
}

async function ProjectRedirect({ params }: Props): Promise<never> {
  const { projectId } = await params
  redirect(`/projects/${encodeURIComponent(projectId)}/research`)
}
