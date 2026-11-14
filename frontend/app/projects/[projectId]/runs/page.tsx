import { ExecutionScreen } from '@/features/execution'
export default async function RunsPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params
  return <ExecutionScreen project_id={projectId} />
}
