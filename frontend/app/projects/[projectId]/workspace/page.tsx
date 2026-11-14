import { WorkspaceScreen } from '@/features/workspace'
export default async function WorkspacePage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params
  return <WorkspaceScreen project_id={projectId} />
}
