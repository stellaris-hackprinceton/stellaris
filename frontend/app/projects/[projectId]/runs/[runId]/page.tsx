import { Suspense } from 'react'
import { ExecutionScreen } from '@/features/execution'
import LoadingProjectView from '../../loading'

type Props = { params: Promise<{ projectId: string, runId: string }> }

export default function RunPage({ params }: Props) {
  return <Suspense fallback={<LoadingProjectView />}><RunPageContent params={params} /></Suspense>
}

async function RunPageContent({ params }: Props) {
  const { projectId, runId } = await params
  return <ExecutionScreen project_id={projectId} run_id={runId} />
}
