import { ResearchSlot } from '@/providers/feature-bridge'
export default async function ResearchPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params
  return <ResearchSlot project_id={projectId} />
}
