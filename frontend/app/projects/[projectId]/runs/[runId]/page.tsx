import { ExecutionScreen } from '@/features/execution'
export default async function RunPage({ params }: { params: Promise<{ projectId: string, runId: string }> }) {
  const { projectId, runId } = await params
  return <ExecutionScreen project_id={projectId} run_id={runId} />
}
