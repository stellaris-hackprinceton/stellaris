import { Suspense } from 'react'
import { StudioSlot } from '@/providers/feature-bridge'
import LoadingProjectView from '../loading'

type Props = { params: Promise<{ projectId: string }> }

export default function StudioPage({ params }: Props) {
  return <Suspense fallback={<LoadingProjectView />}><StudioPageContent params={params} /></Suspense>
}

async function StudioPageContent({ params }: Props) {
  const { projectId } = await params
  return <StudioSlot project_id={projectId} />
}
