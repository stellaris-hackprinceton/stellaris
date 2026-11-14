import { Suspense } from 'react'
import { ResearchSlot } from '@/providers/feature-bridge'
import LoadingProjectView from '../loading'

type Props = { params: Promise<{ projectId: string }> }

export default function ResearchPage({ params }: Props) {
  return <Suspense fallback={<LoadingProjectView />}><ResearchPageContent params={params} /></Suspense>
}

async function ResearchPageContent({ params }: Props) {
  const { projectId } = await params
  return <ResearchSlot project_id={projectId} />
}
