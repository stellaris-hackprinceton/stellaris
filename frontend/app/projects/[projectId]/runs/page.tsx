import { Suspense } from 'react'
import { ExecutionScreen } from '@/features/execution'
import LoadingProjectView from '../loading'

type Props = { params: Promise<{ projectId: string }> }

export default function RunsPage({ params }: Props) {
  return <Suspense fallback={<LoadingProjectView />}><RunsPageContent params={params} /></Suspense>
}

async function RunsPageContent({ params }: Props) {
  const { projectId } = await params
  return <ExecutionScreen project_id={projectId} />
}
